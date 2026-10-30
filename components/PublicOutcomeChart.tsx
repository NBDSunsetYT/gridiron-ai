'use client';

import {Bar,BarChart,CartesianGrid,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';

export default function PublicOutcomeChart({histogram}:{histogram:Array<{value:number;count:number}>}){
 return <figure className="public-distribution" aria-label="Simulated outcome distribution"><ResponsiveContainer width="100%" height="100%"><BarChart data={histogram}><CartesianGrid vertical={false} stroke="#33443b" strokeDasharray="3 5"/><XAxis dataKey="value" minTickGap={25} tick={{fill:'#9fb2a8',fontSize:10}}/><YAxis tick={{fill:'#9fb2a8',fontSize:10}} width={38}/><Tooltip contentStyle={{background:'#12211a',border:'1px solid #35483d',borderRadius:8,fontSize:12}}/><Bar dataKey="count" name="Simulated games" fill="#53e6a6" radius={[3,3,0,0]}/></BarChart></ResponsiveContainer></figure>;
}
