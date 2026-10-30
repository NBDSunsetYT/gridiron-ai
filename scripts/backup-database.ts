/** Run before manual deployments: node --import tsx scripts/backup-database.ts */
import Database from 'better-sqlite3';
import {existsSync} from 'node:fs';import path from 'node:path';
import {backupDatabase} from '../lib/db';
const directory=process.env.DATA_DIR||path.join(process.cwd(),'data');const filename=path.join(directory,'gridiron.sqlite');
if(!existsSync(filename)){console.error('No existing database found. Nothing was changed.');process.exitCode=1;}else{const db=new Database(filename,{readonly:true,fileMustExist:true});try{db.pragma('busy_timeout = 5000');const backup=backupDatabase(db,path.join(directory,'backups'));console.log(JSON.stringify({backupPath:backup,integrity:db.pragma('quick_check',{simple:true})}));}finally{db.close();}}
