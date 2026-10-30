import UIKit
import WebKit
import Security
import Capacitor

// Private credentials never cross the JavaScript bridge. No password is stored.
enum GridironSessionVault {
    static let cookieNames: Set<String> = ["gridiron_session", "gridiron_sb_access", "gridiron_sb_refresh", "gridiron_backend"]
    static let service = "ai.gridiron.personal.session.v1"
    static var origin: URL? {
        guard let text = Bundle.main.object(forInfoDictionaryKey: "GRIDIRON_API_ORIGIN") as? String,
              let url = URL(string: text), url.scheme == "https", let host = url.host,
              !["localhost", "127.0.0.1", "0.0.0.0", "::1"].contains(host), url.user == nil, url.password == nil,
              url.query == nil, url.fragment == nil, url.path.isEmpty || url.path == "/" else { return nil }
        return url
    }
    struct CookieRecord: Codable { let name: String; let value: String; let expires: TimeInterval? }
    struct Snapshot: Codable { let version: Int; let origin: String; let savedAt: TimeInterval; let cookies: [CookieRecord] }
    static func sameOrigin(_ url: URL) -> Bool {
        guard let trusted = origin else { return false }
        return url.scheme == "https" && url.host == trusted.host && (url.port ?? 443) == (trusted.port ?? 443) && url.user == nil && url.password == nil
    }
    static func approved(_ cookie: HTTPCookie) -> Bool {
        guard let host = origin?.host else { return false }
        return cookieNames.contains(cookie.name) && cookie.domain.trimmingCharacters(in: CharacterSet(charactersIn: ".")) == host && cookie.path == "/" && cookie.isSecure && cookie.isHTTPOnly && (cookie.expiresDate == nil || cookie.expiresDate! > Date())
    }
    static func query() -> [String: Any]? {
        guard let url = origin else { return nil }
        return [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: url.absoluteString]
    }
    static func clearSecret() {
        guard let q = query() else { return }
        SecItemDelete(q as CFDictionary)
    }
    static func write(_ cookies: [HTTPCookie]) -> Bool {
        guard let url = origin, let q = query() else { return false }
        let approvedCookies = cookies.filter(approved)
        if approvedCookies.isEmpty { clearSecret(); return true }
        let snapshot = Snapshot(version: 1, origin: url.absoluteString, savedAt: Date().timeIntervalSince1970,
                                cookies: approvedCookies.map { CookieRecord(name: $0.name, value: $0.value, expires: $0.expiresDate?.timeIntervalSince1970) })
        guard let encoded = try? JSONEncoder().encode(snapshot), encoded.count < 40_000 else { return false }
        let attributes: [String: Any] = [kSecValueData as String: encoded, kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        let updated = SecItemUpdate(q as CFDictionary, attributes as CFDictionary)
        if updated == errSecItemNotFound {
            var added = q; attributes.forEach { added[$0.key] = $0.value }
            return SecItemAdd(added as CFDictionary, nil) == errSecSuccess
        }
        return updated == errSecSuccess
    }
    static func read() -> Snapshot? {
        guard var q = query(), let url = origin else { return nil }
        q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var value: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &value) == errSecSuccess, let bytes = value as? Data, bytes.count < 40_000,
              let snapshot = try? JSONDecoder().decode(Snapshot.self, from: bytes), snapshot.version == 1,
              snapshot.origin == url.absoluteString, snapshot.cookies.count <= cookieNames.count,
              Date().timeIntervalSince1970 - snapshot.savedAt <= 30 * 86_400 else { return nil }
        return snapshot
    }
    static func restore(to store: WKHTTPCookieStore, completion: @escaping (Int, Bool) -> Void) {
        guard let url = origin else { completion(0, false); return }
        store.getAllCookies { current in
            let present = current.filter(approved)
            if present.contains(where: { $0.name != "gridiron_backend" }) { _ = write(present); completion(present.count, false); return }
            guard let saved = read() else { completion(0, false); return }
            let group = DispatchGroup(); var restored = 0
            for record in saved.cookies {
                if record.name == "gridiron_backend" && present.contains(where: { $0.name == "gridiron_backend" }) { continue }
                guard cookieNames.contains(record.name), !record.value.contains(where: { $0 == ";" || $0 == "\r" || $0 == "\n" }), record.expires == nil || record.expires! > Date().timeIntervalSince1970 else { continue }
                var header = "\(record.name)=\(record.value); Path=/; Secure; HttpOnly; SameSite=Lax"
                if let expiry = record.expires {
                    let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX"); formatter.timeZone = TimeZone(secondsFromGMT: 0); formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss 'GMT'"
                    header += "; Expires=" + formatter.string(from: Date(timeIntervalSince1970: expiry))
                }
                guard let cookie = HTTPCookie.cookies(withResponseHeaderFields: ["Set-Cookie": header], for: url).first, approved(cookie) else { continue }
                group.enter(); restored += 1; store.setCookie(cookie) { group.leave() }
            }
            group.notify(queue: .main) { completion(restored, restored > 0) }
        }
    }
}

// The gate restores Keychain cookies before a Capacitor WebView is constructed or loads the application.
final class GridironRootViewController: UIViewController {
    private var appController: GridironBridgeViewController?
    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }
    override func viewDidLoad() {
        super.viewDidLoad(); view.backgroundColor = UIColor(red: 9/255, green: 13/255, blue: 12/255, alpha: 1)
        let title = UILabel(); title.text = "GRIDIRON AI"; title.textColor = UIColor(red: 84/255, green: 232/255, blue: 165/255, alpha: 1); title.font = .systemFont(ofSize: 25, weight: .bold); title.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(title); NSLayoutConstraint.activate([title.centerXAnchor.constraint(equalTo: view.centerXAnchor), title.centerYAnchor.constraint(equalTo: view.centerYAnchor)])
        GridironSessionVault.restore(to: WKWebsiteDataStore.default().httpCookieStore) { [weak self] _, _ in
            guard let self = self, self.appController == nil else { return }
            let app = GridironBridgeViewController(); self.appController = app; self.addChild(app)
            app.view.frame = self.view.bounds; app.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]; self.view.addSubview(app.view); app.didMove(toParent: self); title.removeFromSuperview()
        }
    }
}

final class GridironBridgeViewController: CAPBridgeViewController {
    override func webViewConfiguration(for instanceConfiguration: InstanceConfiguration) -> WKWebViewConfiguration {
        let config = super.webViewConfiguration(for: instanceConfiguration)
        config.websiteDataStore = WKWebsiteDataStore.default()
        return config
    }
    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(GridironSessionPlugin())
        webView?.allowsBackForwardNavigationGestures = true
        webView?.scrollView.backgroundColor = UIColor(red: 9/255, green: 13/255, blue: 12/255, alpha: 1)
    }
}

@objc(GridironSessionPlugin)
public final class GridironSessionPlugin: CAPPlugin, CAPBridgedPlugin, WKHTTPCookieStoreObserver {
    public let identifier = "GridironSessionPlugin"
    public let jsName = "GridironSession"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "capture", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "restore", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "clear", returnType: CAPPluginReturnPromise)]
    private var pendingCapture: DispatchWorkItem?
    private var backgroundObserver: NSObjectProtocol?
    public override func load() {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            // The root gate has already completed restoration before this plugin is constructed.
            self.webView?.configuration.websiteDataStore.httpCookieStore.add(self)
            self.backgroundObserver = NotificationCenter.default.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in
                guard let self = self, self.trustedPage(), let store = self.webView?.configuration.websiteDataStore.httpCookieStore else { return }
                self.pendingCapture?.cancel()
                var task = UIBackgroundTaskIdentifier.invalid
                task = UIApplication.shared.beginBackgroundTask(withName: "Save private session") { if task != .invalid { UIApplication.shared.endBackgroundTask(task); task = .invalid } }
                store.getAllCookies { cookies in
                    _ = GridironSessionVault.write(cookies)
                    if task != .invalid { UIApplication.shared.endBackgroundTask(task); task = .invalid }
                }
            }
        }
    }
    deinit { if let observer = backgroundObserver { NotificationCenter.default.removeObserver(observer) } }
    private func trustedPage() -> Bool { guard let url = webView?.url else { return false }; return GridironSessionVault.sameOrigin(url) }
    @objc public func status(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in guard let self = self, self.trustedPage() else { call.reject("Native session is restricted to the configured HTTPS application."); return }; call.resolve(["configured": true, "keychain": true, "pushEntitlement": (Bundle.main.object(forInfoDictionaryKey: "GRIDIRON_PUSH_ENABLED") as? Bool) == true, "apnsEnvironment": Bundle.main.object(forInfoDictionaryKey: "GRIDIRON_APNS_ENV") as? String ?? "development"]) }
    }
    @objc public func capture(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self, self.trustedPage(), let store = self.webView?.configuration.websiteDataStore.httpCookieStore else { call.reject("Untrusted native session origin."); return }
            store.getAllCookies { cookies in
                let kept = cookies.filter(GridironSessionVault.approved)
                if GridironSessionVault.write(kept) { call.resolve(["stored": kept.count]) } else { call.reject("Keychain is unavailable while this device is locked.") }
            }
        }
    }
    @objc public func restore(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in guard let self = self, self.trustedPage(), let store = self.webView?.configuration.websiteDataStore.httpCookieStore else { call.reject("Untrusted native session origin."); return }; GridironSessionVault.restore(to: store) { count, changed in call.resolve(["restored": count, "changed": changed]) } }
    }
    @objc public func clear(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self, self.trustedPage(), let store = self.webView?.configuration.websiteDataStore.httpCookieStore else { call.reject("Untrusted native session origin."); return }
            GridironSessionVault.clearSecret(); store.getAllCookies { cookies in
                let routing = cookies.filter { GridironSessionVault.approved($0) && $0.name == "gridiron_backend" }
                let group = DispatchGroup()
                for cookie in cookies where GridironSessionVault.approved(cookie) && cookie.name != "gridiron_backend" { group.enter(); store.delete(cookie) { group.leave() } }
                group.notify(queue: .main) { _ = GridironSessionVault.write(routing); call.resolve(["cleared": true, "workspaceRetained": !routing.isEmpty]) }
            }
        }
    }
    public func cookiesDidChange(in cookieStore: WKHTTPCookieStore) {
        pendingCapture?.cancel(); let item = DispatchWorkItem { [weak self] in guard self?.trustedPage() == true else { return }; cookieStore.getAllCookies { _ = GridironSessionVault.write($0) } }; pendingCapture = item; DispatchQueue.main.asyncAfter(deadline: .now() + 0.2, execute: item)
    }
    @objc public override func shouldOverrideLoad(_ navigationAction: WKNavigationAction) -> NSNumber? {
        guard let url = navigationAction.request.url else { return NSNumber(value: true) }
        if GridironSessionVault.sameOrigin(url) { return nil }
        // The bundled setup screen is allowed only when no release origin was configured.
        if GridironSessionVault.origin == nil && url.scheme == "capacitor" { return nil }
        let topLevel = navigationAction.targetFrame == nil || navigationAction.targetFrame?.isMainFrame == true
        if topLevel && ["https", "http", "mailto", "tel"].contains(url.scheme ?? "") { DispatchQueue.main.async { UIApplication.shared.open(url, options: [:], completionHandler: nil) } }
        return NSNumber(value: true)
    }
}
