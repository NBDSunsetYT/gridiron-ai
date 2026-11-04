export type RetentionAsset={id:string;kind:string;expiresAt:string|null;protected:boolean;referenced:boolean;backup:{verified:boolean;sha256:string}|null;sha256:string};
const deletable=new Set(['cache','temporary_dataset','temporary_simulation','failed_intermediate']);
/** Planning only. No database, bucket or accounting deletion is performed. */
export function retentionPlan(assets:RetentionAsset[],now=Date.now()){
 return assets.map(asset=>{const eligible=deletable.has(asset.kind)&&!asset.protected&&!asset.referenced&&Number.isFinite(Date.parse(asset.expiresAt??''))&&Date.parse(asset.expiresAt!)<now&&asset.backup?.verified===true&&asset.backup.sha256===asset.sha256;
 return{id:asset.id,eligible,action:eligible?'review_verified_temporary_copy':'retain',reason:eligible?'Expired, unreferenced, disposable copy with a verified matching backup.':'Protected, referenced, unexpired, permanent, or missing verified backup.'};});
}
