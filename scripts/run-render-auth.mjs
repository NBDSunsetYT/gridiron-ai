/** Never emits passwords. Execute only after the operator confirms Auth URLs. */
import {spawn} from 'node:child_process';
import {readFixture} from './prepare-render-qa.mjs';
if(!process.argv.includes('--allowlist-confirmed')){
 console.error('Auth acceptance is gated until the Render redirect allowlist is confirmed. No login or write was attempted.');process.exitCode=2;
}else{
 const {value}=readFixture();if(value.accounts.length!==2||value.accounts.some(a=>!a.id))throw Error('Provisioned disposable identities are required');
 const child=spawn(process.execPath,['scripts/verify-render-auth.mjs'],{stdio:['pipe','inherit','inherit']});
 child.stdin.end(JSON.stringify({approvedDisposable:true,accounts:value.accounts,mode:process.argv.includes('--reopen')?'reopen':'initial'})+'\n');
 child.on('exit',code=>process.exitCode=code??1);
}
