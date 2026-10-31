import {z} from 'zod';
export const legSchema=z.object({id:z.string().max(200),player:z.string().max(150).default(''),event:z.string().min(1).max(200),market:z.string().min(1).max(100),selection:z.string().min(1).max(250),threshold:z.string().max(40).default(''),source:z.string().max(150).default('Manual hypothetical selection'),sourceQuote:z.record(z.string(),z.unknown()).optional(),currentQuote:z.record(z.string(),z.unknown()).nullable().optional(),originalProbability:z.number().min(0).max(1).nullable().default(null)}).strict();
const money=z.string().regex(/^(0|[1-9]\d{0,6})(\.\d{1,2})?$/);
export const workspaceDataSchema=z.object({name:z.string().min(1).max(120),notes:z.string().max(5000),legs:z.array(legSchema).max(12),amount:money,multiplier:z.string().regex(/^(0|[1-9]\d{0,5})(\.\d{1,6})?$/),fees:money,pricingBasis:z.literal('user_hypothetical'),body:z.string().max(20000).default('')}).strict();
export const workspaceSaveSchema=z.object({id:z.string().uuid(),mutationId:z.string().uuid(),expectedRevision:z.number().int().nonnegative(),sport:z.enum(['NFL','CFB']),kind:z.enum(['combination','research']),data:workspaceDataSchema}).strict();
export type WorkspaceData=z.infer<typeof workspaceDataSchema>;
export type WorkspaceSave=z.infer<typeof workspaceSaveSchema>;
export const blankWorkspace=():WorkspaceData=>({name:'My combination',notes:'',legs:[],amount:'20',multiplier:'3.50',fees:'0',pricingBasis:'user_hypothetical',body:''});
