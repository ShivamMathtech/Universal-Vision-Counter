import {useEffect,useState} from 'react';
import {Stats,emptyStats} from '../services/api';
export function useDetection(){
 const [stats,setStats]=useState<Stats>(emptyStats),[online,setOnline]=useState(false);
 useEffect(()=>{let stopped=false,ws:WebSocket,timer:ReturnType<typeof setTimeout>;
 const connect=()=>{ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/ws`);
 ws.onopen=()=>setOnline(true);ws.onmessage=e=>{try{setStats(JSON.parse(e.data))}catch{}};
 ws.onclose=()=>{setOnline(false);if(!stopped)timer=setTimeout(connect,1800)};ws.onerror=()=>ws.close()};connect();
 return()=>{stopped=true;clearTimeout(timer);ws?.close()};},[]);
 return {stats,setStats,online};
}
