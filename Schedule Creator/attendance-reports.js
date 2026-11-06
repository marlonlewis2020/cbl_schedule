(()=>{
    let active=null,busy=false;
    async function request(method='GET',body){
        const state=method==='GET'?null:await (await fetch('/api/tenant-auth/state',{cache:'no-store'})).json();
        const response=await fetch('/api/attendance/reports',{method,cache:'no-store',
            headers:{'Content-Type':'application/json',...(state?{'X-CSRF-Token':state.csrfToken}:{})},
            ...(body===undefined?{}:{body:JSON.stringify(body)})});
        const data=await response.json();if(!response.ok)throw Error(data.error||'Report request failed.');return data;
    }
    async function mount(node){
        active=node;
        const heading=document.createElement('h2');heading.textContent='Attendance snapshots';
        const intro=document.createElement('p');intro.textContent='Interactive HTML dashboards and immutable XLSX downloads at 7 AM, 3 PM and 11 PM Jamaica time, or on demand. HTML includes executive KPIs, charts, filters and employee exceptions, and works offline. A separately running report worker is required. Automatic email is deferred.';
        const actions=document.createElement('div');actions.className='actions';
        const capture=document.createElement('button'),refresh=document.createElement('button'),toggle=document.createElement('button');
        capture.type=refresh.type=toggle.type='button';capture.textContent='Capture now';refresh.textContent='Refresh history';
        const status=document.createElement('p');status.setAttribute('role','status');
        const list=document.createElement('div');list.className='tablewrap';
        actions.append(capture,refresh,toggle);node.replaceChildren(heading,intro,actions,status,list);
        let enabled=false;
        async function load(){
            const data=await request();enabled=data.enabled;toggle.textContent=enabled?'Disable scheduled captures':'Enable scheduled captures';
            status.textContent=`${data.emailStatus} Worker last seen: ${data.heartbeat?new Date(data.heartbeat).toLocaleString():'not yet connected'}.`;
            const table=document.createElement('table'),thead=document.createElement('thead'),header=document.createElement('tr');
            ['Scheduled cutoff (Jamaica)','Captured at (Jamaica)','State','Details','Reports'].forEach(text=>{const th=document.createElement('th');th.textContent=text;header.append(th);});thead.append(header);table.append(thead);
            const tbody=document.createElement('tbody');
            for(const report of data.reports){
                const row=document.createElement('tr');
                for(const text of [report.cutoff,report.createdAt,report.state,report.error||'']){
                    const td=document.createElement('td');td.textContent=text;row.append(td);
                }
                const td=document.createElement('td');
                if(['ready','stale'].includes(report.state)){
                    const base=`/api/attendance/reports/${encodeURIComponent(report.id)}`;
                    const links=document.createElement('div');links.className='actions';
                    for(const [text,suffix] of [['View HTML','/html'],['Download HTML','/html/download'],['Download XLSX','/download']]){
                        const link=document.createElement('a');link.textContent=text+(report.state==='stale'?' (stale source)':'');link.href=base+suffix;
                        if(suffix==='/html'){link.target='_blank';link.rel='noopener noreferrer';}
                        links.append(link);
                    }
                    td.append(links);
                }
                row.append(td);tbody.append(row);
            }
            if(!data.reports.length){const row=document.createElement('tr'),td=document.createElement('td');td.colSpan=5;td.textContent='No snapshots captured yet.';row.append(td);tbody.append(row);}
            table.append(tbody);list.replaceChildren(table);
        }
        async function action(fn){
            if(busy)return;busy=true;capture.disabled=refresh.disabled=toggle.disabled=true;
            try{await fn();}catch(error){status.textContent=error.message;}finally{busy=false;capture.disabled=refresh.disabled=toggle.disabled=false;}
        }
        capture.onclick=()=>void action(async()=>{status.textContent='Refreshing source and capturing snapshot...';await request('POST',{});await load();});
        refresh.onclick=()=>void action(load);
        toggle.onclick=()=>void action(async()=>{await request('PUT',{enabled:!enabled});await load();});
        try{await load();}catch(error){status.textContent=error.message;capture.disabled=toggle.disabled=true;}
    }
    new MutationObserver(()=>{
        const node=document.getElementById('attendanceReports');
        if(node&&node!==active)void mount(node);
        else if(!node)active=null;
    }).observe(document.body,{childList:true,subtree:true});
})();
