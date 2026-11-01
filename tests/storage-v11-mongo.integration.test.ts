/** Real local MongoDB engine, isolated synthetic documents. Not an Atlas authorization test. */
import {afterAll,beforeAll,describe,expect,it} from 'vitest';
import {MongoMemoryServer} from 'mongodb-memory-server-core';
import {MongoClient} from 'mongodb';
import {MongoResearchRepository} from '../lib/storage/mongo';
import {researchDocument} from '../lib/storage/schema';
let server:MongoMemoryServer,client:MongoClient,repository:MongoResearchRepository;
beforeAll(async()=>{server=await MongoMemoryServer.create();client=await new MongoClient(server.getUri()).connect();repository=new MongoResearchRepository(client.db('gridiron_synthetic_research'));await repository.ensureIndexes();},120000);
afterAll(async()=>{await client?.close();await server?.stop();});
describe('actual local MongoDB research operations',()=>{
 it('inserts once, retrieves integrity-checked NFL/CFB documents and paginates by stable cursor',async()=>{for(const sport of['NFL','CFB'] as const)for(let i=0;i<4;i++){const document=researchDocument(sport,'SYNTHETIC-GAME','matchup_report',{observedAt:`2026-01-0${i+1}T00:00:00Z`,note:`SYNTHETIC ${sport} ${i}`});await repository.put(document);await repository.put(document);expect(await repository.get(document._id,document.sha256)).toEqual(document.payload);}const first=await repository.page('NFL','SYNTHETIC-GAME',undefined,2),second=await repository.page('NFL','SYNTHETIC-GAME',first.next!,2);expect(first.rows).toHaveLength(2);expect(second.rows).toHaveLength(2);expect(new Set([...first.rows,...second.rows].map(x=>x._id)).size).toBe(4);expect((await repository.usage()).objects).toBe(8);});
 it('never overwrites an immutable identity with changed payloads',async()=>{const document=researchDocument('NFL','SYNTHETIC-IMMUTABLE','explanation',{note:'SYNTHETIC original'});await repository.put(document);await expect(repository.put({...document,payload:{note:'SYNTHETIC changed'}})).rejects.toThrow('integrity');expect(await repository.get(document._id,document.sha256)).toEqual(document.payload);});
});
