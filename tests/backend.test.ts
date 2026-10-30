import {describe,it,expect} from 'vitest';
import {selectedBackend} from '../lib/backend';
describe('Explicit data workspace selection',()=>{
 it('preserves SQLite when cloud has not been selected',()=>{expect(selectedBackend(undefined,'')).toBe('sqlite');expect(selectedBackend('invalid','')).toBe('sqlite');});
 it('uses explicit selection without silently falling back from cloud',()=>{expect(selectedBackend('supabase','sqlite')).toBe('supabase');expect(selectedBackend('sqlite','supabase')).toBe('sqlite');expect(selectedBackend(null,'supabase')).toBe('supabase');});
});
