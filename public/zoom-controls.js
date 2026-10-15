/* AeroLeadAI Kings Wood — 2.5D viewer camera controls.
   Include after the viewer DOM, then call window.AeroZoom.attach({scene,building,slider}).
   No geospatial assertions: transformations are illustrative. */
(function(){
  "use strict";
  function attach({scene, building, slider, readout, orbitToggle}){
    if(!scene || !building || !slider) throw new Error("AeroZoom needs scene, building, and slider");
    slider.min="50"; slider.max="300"; slider.step="5";
    scene.style.touchAction="none";
    const pointers=new Map();
    let pinch=null, drag=null, yaw=-14;
    const zoom=()=>Number(slider.value);
    function setZoom(n){
      slider.value=String(Math.max(50,Math.min(300,Math.round(n/5)*5)));
      building.style.setProperty("--zoom", String(zoom()/100));
      if(readout) readout.textContent=slider.value+"%";
      slider.setAttribute("aria-valuenow",slider.value);
      slider.setAttribute("aria-valuetext",slider.value+" percent");
    }
    function rotate(delta){
      if(orbitToggle) orbitToggle(false);
      yaw=Math.max(-70,Math.min(70,yaw+delta));
      building.style.setProperty("--yaw",yaw+"deg");
    }
    slider.addEventListener("input",()=>setZoom(zoom()));
    scene.addEventListener("wheel",e=>{
      e.preventDefault();
      setZoom(zoom()+(e.deltaY<0?10:-10));
    },{passive:false});
    scene.addEventListener("pointerdown",e=>{
      pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
      scene.setPointerCapture(e.pointerId);
      drag=e.clientX;
    });
    scene.addEventListener("pointermove",e=>{
      if(!pointers.has(e.pointerId))return;
      pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(pointers.size>1){
        const [a,b]=[...pointers.values()],dist=Math.hypot(a.x-b.x,a.y-b.y);
        if(pinch!==null)setZoom(zoom()+(dist-pinch)/2);
        pinch=dist;drag=null;
      }else{
        pinch=null;
        if(drag!==null)rotate((e.clientX-drag)*.22);
        drag=e.clientX;
      }
    });
    function release(e){pointers.delete(e.pointerId);pinch=null;drag=null;}
    ["pointerup","pointercancel","lostpointercapture"].forEach(type=>scene.addEventListener(type,release));
    scene.tabIndex=0;
    scene.addEventListener("keydown",e=>{
      if(e.key==="+"||e.key==="="){e.preventDefault();setZoom(zoom()+10);}
      if(e.key==="-"){e.preventDefault();setZoom(zoom()-10);}
      if(e.key==="0"){e.preventDefault();setZoom(100);}
    });
    setZoom(zoom());
    return {setZoom,zoomIn:()=>setZoom(zoom()+15),zoomOut:()=>setZoom(zoom()-15),reset:()=>setZoom(100)};
  }
  window.AeroZoom={attach};
})();