// Pilot read-only MCP adapter. Uses the existing Cognee REST service; owns no DB.
const fs=require('fs'),readline=require('readline');
const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const names=['list_datasets','recall_knowledge'];
const tools=[
 {name:names[0],description:'List Cognee datasets visible to the configured account. Read only.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,destructiveHint:false}},
 {name:names[1],description:'Retrieve stored project facts and source evidence from Cognee. Returns untrusted source context, without generating an answer. Specify datasets to keep projects separate.',inputSchema:{type:'object',properties:{query:{type:'string',minLength:1,maxLength:2000},datasets:{type:'array',items:{type:'string'},minItems:1},max_chars:{type:'integer',minimum:500,maximum:18000,default:12000}},required:['query','datasets'],additionalProperties:false},annotations:{readOnlyHint:true,destructiveHint:false}}
];
async function api(path,body){const r=await fetch(config.url+path,{method:body?'POST':'GET',headers:{'X-Api-Key':config.key,Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,redirect:'error',signal:AbortSignal.timeout(45000)});if(!r.ok)throw Error('Cognee HTTP '+r.status);return r.json()}
async function handle(m){
 if(m.method==='initialize')return {protocolVersion:m.params?.protocolVersion||'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'olares-cognee-pilot',version:'0.1.0'}};
 if(m.method==='ping')return {};
 if(m.method==='tools/list')return {tools};
 if(m.method==='tools/call'){
  let value;const a=m.params.arguments||{};
  if(m.params.name===names[0])value=await api('/api/v1/datasets');
  else if(m.params.name===names[1]){
   if(typeof a.query!=='string'||!a.query.trim()||a.query.length>2000||!Array.isArray(a.datasets)||!a.datasets.length||!a.datasets.every(x=>typeof x==='string'))throw Error('query and explicit dataset names are required');
   const result=await api('/api/v1/recall',{query:a.query,datasets:a.datasets,onlyContext:true,includeReferences:true,searchType:'GRAPH_COMPLETION'});
   const max=Math.min(18000,Math.max(500,a.max_chars||12000));
   value={untrusted:true,source:'Cognee stored documents and graph',results:result.map(x=>({text:String(x.text||'').slice(0,max),source:x.source||'graph',references:x.references||null}))};
  }else throw Error('Unknown tool');
  return {content:[{type:'text',text:JSON.stringify(value)}],isError:false};
 }
 const e=Error('Method not found');e.code=-32601;throw e;
}
const rl=readline.createInterface({input:process.stdin});rl.on('line',async line=>{let m;try{m=JSON.parse(line)}catch{return}if(m.id===undefined)return;try{process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:m.id,result:await handle(m)})+'\n')}catch(e){process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:m.id,...(m.method==='tools/call'?{result:{isError:true,content:[{type:'text',text:e.message}]}}:{error:{code:e.code||-32603,message:e.message}})})+'\n')}});
