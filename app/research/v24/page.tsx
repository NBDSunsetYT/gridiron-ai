import {notFound} from 'next/navigation';
import snapshot from '../../../docs/research/dynamic-v24-dashboard.json';
import Dashboard from './research-dashboard';

export const dynamic='force-dynamic';
export default function V24ResearchPage(){
  if(process.env.GRIDIRON_RESEARCH_V24!=='1') notFound();
  return <Dashboard snapshot={snapshot}/>;
}
