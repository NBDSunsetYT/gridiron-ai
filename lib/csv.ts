/** Bounded RFC4180-style CSV parsing shared by verified imports. */
export function parseCSVRecords(source:string,maxRows=1000):Record<string,string>[] {
 if(typeof source!=='string'||new TextEncoder().encode(source).length>1_000_000)throw Error('Choose a CSV smaller than 1 MB.');
 const rows:string[][]=[];let row:string[]=[],cell='',quoted=false,closed=false;
 for(let i=0;i<source.length;i++){const ch=source[i];
  if(quoted){if(ch==='"'){if(source[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=ch;continue;}
  if(ch==='"'){if(cell.length||closed)throw Error('A CSV quote must begin a field.');quoted=true;continue;}
  if(ch===','){row.push(cell);cell='';closed=false;continue;}
  if(ch==='\n'||ch==='\r'){if(ch==='\r'&&source[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v.trim()))rows.push(row);row=[];cell='';closed=false;if(rows.length>maxRows+1)throw Error(`Import no more than ${maxRows} rows.`);continue;}
  if(closed){if(ch===' '||ch==='\t')continue;throw Error('Unexpected text after a closing CSV quote.');}cell+=ch;
 }
 if(quoted)throw Error('Unclosed CSV quote.');row.push(cell);if(row.some(v=>v.trim()))rows.push(row);
 if(rows.length<2)throw Error('CSV requires a header and at least one data row.');
 if(rows.length>maxRows+1)throw Error(`Import no more than ${maxRows} rows.`);
 const header=rows.shift()!.map(h=>h.replace(/^\uFEFF/,'').trim());if(header.some(h=>!h)||new Set(header).size!==header.length)throw Error('CSV headers must be nonempty and unique.');
 return rows.map((values,i)=>{if(values.length!==header.length)throw Error(`CSV row ${i+2} has ${values.length} fields; expected ${header.length}.`);return Object.fromEntries(header.map((h,j)=>[h,values[j].trim()]));});
}
