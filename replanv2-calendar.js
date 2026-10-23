/* Calendar reconciliation is isolated so stale-event cleanup can be tested offline. */
(function(root){
  'use strict';
  async function sync(api, path, rows, events, planId, eventId, scope) {
    const current=new Set();
    // Upsert everything first. Failed uploads never trigger cleanup.
    for(let i=0;i<rows.length;i++) {
      const id=await eventId(rows[i]); current.add(id);
      const event={...events[i],extendedProperties:{private:{...events[i].extendedProperties?.private,replanPlan:planId}}};
      try {await api(path,'POST',{...event,id});}
      catch(error){if(error.status===409)await api(path+'/'+id,'PUT',event);else throw error;}
    }
    // Partial exports cannot express the user's complete desired calendar.
    if(scope!=='all')return {synced:rows.length,removed:0};
    const stale=[];let token='';
    do {
      const page=await api(path+'?maxResults=2500&privateExtendedProperty='+encodeURIComponent('replanPlan='+planId)+(token?'&pageToken='+encodeURIComponent(token):''));
      for(const event of page.items||[])if(event.extendedProperties?.private?.replanPlan===planId&&!current.has(event.id))stale.push(event.id);
      token=page.nextPageToken||'';
    }while(token);
    let removed=0;
    for(const id of stale){try{await api(path+'/'+encodeURIComponent(id),'DELETE');removed++;}catch(e){if(e.status!==404&&e.status!==410)throw e;}}
    return {synced:rows.length,removed};
  }
  const api={sync};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ReplanCalendar=api;
})(globalThis);
