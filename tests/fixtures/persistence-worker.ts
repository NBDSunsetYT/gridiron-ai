import { randomUUID } from 'node:crypto';
import { getDb, closeDb } from '../../lib/db';
import { digest, getUser, newSession, SESSION_COOKIE } from '../../lib/auth';
import { getLedger, postTransaction } from '../../lib/ledger';
import { appendMessage, createConversation, createResearchRecord, getConversation, getPreferences, listConversations, listResearchRecords, setPreference } from '../../lib/research-store';

async function main() {
  const action = process.argv[2];
  if (action === 'seed') {
    const userId = randomUUID(); const otherUserId = randomUUID();
    for (const id of [userId, otherUserId]) {
      getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)')
        .run(id, `${id}@example.test`, 'restart-fixture-hash', new Date().toISOString());
    }
    const token = newSession(userId);
    postTransaction(userId, { type: 'starting_balance', amount: '500.00', sportsbook: 'DraftKings' });
    postTransaction(userId, { type: 'deposit', amount: '40.25', sportsbook: 'Hard Rock', reference: 'restart-import-1' });
    const conversation = createConversation(userId, 'Persistent NFL research');
    appendMessage(userId, conversation.id, { role: 'user', content: 'Explain my recorded bankroll.' });
    appendMessage(userId, conversation.id, { role: 'assistant', content: 'Your recorded balance is $540.25.', data: { source: 'personal-ledger' } });
    setPreference(userId, 'theme', 'dark');
    setPreference(userId, 'favoriteTeams', ['KC', 'BUF']);
    const research = createResearchRecord(userId, { kind: 'saved-analysis', entityKey: 'test-user-entry', data: { note: 'User-provided research; no fabricated source.', probability: 0.6 }, source: 'manual', observedAt: '2026-01-01T00:00:00Z' });
    const session = getDb().prepare('SELECT token_hash FROM sessions WHERE user_id=?').get(userId) as { token_hash: string };
    console.log(JSON.stringify({ userId, otherUserId, token, conversationId: conversation.id, researchId: research.id, sessionDigest: session.token_hash, expectedDigest: digest(token) }));
  } else if (action === 'read') {
    const state = JSON.parse(process.argv[3]);
    const user = await getUser(new Request('http://localhost/api/account', { headers: { cookie: `${SESSION_COOKIE}=${state.token}` } }));
    let forbiddenStatus: number | null = null;
    try { getConversation(state.otherUserId, state.conversationId); } catch (error) {
      forbiddenStatus = (error as { status?: number }).status ?? null;
    }
    console.log(JSON.stringify({
      user, ledger: getLedger(state.userId), conversation: getConversation(state.userId, state.conversationId),
      conversations: listConversations(state.userId), preferences: getPreferences(state.userId), research: listResearchRecords(state.userId, { kind: 'saved-analysis' }),
      strangerLedger: getLedger(state.otherUserId), strangerConversations: listConversations(state.otherUserId), strangerPreferences: getPreferences(state.otherUserId), strangerResearch: listResearchRecords(state.otherUserId, {}), forbiddenStatus,
    }));
  } else throw new Error('Unknown persistence fixture action.');
  closeDb();
}
main().catch((error) => {
  console.error(error instanceof Error ? error.stack : String(error));
  closeDb(); process.exitCode = 1;
});
