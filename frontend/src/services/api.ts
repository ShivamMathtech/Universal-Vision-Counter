export async function api<T=any>(path:string, method='GET',body?:unknown):Promise<T>{
 const form=body instanceof FormData;
 const response=await fetch('/api'+path,{method,headers:body&&!form?{'Content-Type':'application/json'}:undefined,body:body?(form?body:JSON.stringify(body)):undefined});
 if(!response.ok){let message=`Request failed (${response.status})`;try{const data=await response.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)}catch{}throw new Error(message)}
 return response.json();
}
export function upload(path:string,file:File){const data=new FormData();data.append('file',file);return api(path,'POST',data)}
export type Point=[number,number];
export type Zone={name:string,points:Point[]};
export type Stats={session_id:string|null,status:string,error:string|null,source_kind:string|null,total_unique:number,current_total:number,
 classes:Record<string,number>,current_classes:Record<string,number>,entered:number,exited:number,currently_inside:number,net_flow:number,zones:Record<string,number>,
 display_fps:number,video_fps:number,inference_fps:number,inference_ms:number,latency_ms:number,cpu:number,ram_gb:number|null,system_ram_percent:number,dropped_frames:number,skipped_frames:number,queue_size:number,
 image_size:number,model:string|null,backend:string,confidence:number,position:number,duration:number,speed:number,recording:boolean,recording_file:string|null,
 series:{time:number,current:number,unique:number}[],recent:{timestamp:number,class_name:string,id:number,confidence:number}[],detections:any[],line:Point[]|null,zone_config:Zone[],image_url?:string,original_url?:string};
export const emptyStats:Stats={session_id:null,status:'idle',error:null,source_kind:null,total_unique:0,current_total:0,classes:{},current_classes:{},entered:0,exited:0,currently_inside:0,net_flow:0,zones:{},display_fps:0,video_fps:0,inference_fps:0,inference_ms:0,latency_ms:0,cpu:0,ram_gb:0,system_ram_percent:0,dropped_frames:0,skipped_frames:0,queue_size:0,image_size:416,model:null,backend:'cpu',confidence:0,position:0,duration:0,speed:1,recording:false,recording_file:null,series:[],recent:[],detections:[],line:null,zone_config:[]};
