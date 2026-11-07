(()=>{
    let active=null,busy=false;
    function mountTableDownloads(){
        const anchor=document.getElementById('attendanceReports');
        if(!anchor)return;
        const page=anchor.closest('main');
        if(!page)return;
        for(const table of page.querySelectorAll('table')){
            if(table.dataset.excelDownload||table.closest('dialog'))continue;
            table.dataset.excelDownload='true';
            const section=table.closest('.panel,section');
            const title=section?.querySelector('h2,h3')?.textContent||'Attendance table';
            const button=document.createElement('button');button.type='button';button.textContent='Download Excel';
            button.setAttribute('aria-label',`Download Excel: ${title}`);
            button.onclick=()=>{
                try{
                    const headers=[...table.querySelectorAll('thead tr:first-child th')];
                    const columns=headers.map((cell,index)=>({cell,index})).filter(({cell})=>
                        !cell.querySelector('input')&&!/^(Actions|Resolution|Reports|Downloads)$/i.test(cell.textContent.trim()));
                    const text=cell=>{
                        if(!cell)return '';
                        const clone=cell.cloneNode(true);
                        clone.querySelectorAll('button,input,select,a').forEach(node=>node.remove());
                        clone.querySelectorAll('small,br,p').forEach(node=>node.before(document.createTextNode(' ')));
                        return clone.textContent.replace(/\s+/g,' ').trim();
                    };
                    const rows=[columns.map(({cell})=>cell.textContent.replace(/[▲▼]/g,'').trim())];
                    for(const row of table.querySelectorAll('tbody tr')){
                        if(row.cells.length!==headers.length||row.hidden)continue;
                        rows.push(columns.map(({index})=>text(row.cells[index])));
                    }
                    downloadFile('Attendance-'+title.replace(/[^a-z0-9]+/gi,'-').slice(0,80)+'.xlsx',workbookBlob({Attendance:rows}));
                }catch(error){window.alert('Unable to download this table: '+error.message);}
            };
            const wrapper=table.closest('.tablewrap,.scroll')||table;
            wrapper.before(button);
        }
    }
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
        const capture=document.createElement('button'),refresh=document.createElement('button'),toggle=document.createElement('button'),remove=document.createElement('button');
        capture.type=refresh.type=toggle.type=remove.type='button';capture.textContent='Capture now';refresh.textContent='Refresh history';remove.textContent='Delete selected';remove.disabled=true;
        const status=document.createElement('p');status.setAttribute('role','status');
        const list=document.createElement('div');list.className='tablewrap';
        const emailPanel=document.createElement('section');emailPanel.hidden=true;
        actions.append(capture,refresh,toggle,remove);node.replaceChildren(heading,intro,actions,status,list,emailPanel);
        const selected=new Set();
        const updateSelection=()=>{remove.disabled=busy||!selected.size;remove.textContent=`Delete selected (${selected.size})`;};
        async function showEmail(id){
            const response=await fetch(`/api/attendance/reports/${encodeURIComponent(id)}/email`,{cache:'no-store'});
            const data=await response.json();if(!response.ok)throw Error(data.error||'Email generation failed.');
            const title=document.createElement('h3');title.textContent='Email body preview';
            const subject=document.createElement('input');subject.readOnly=true;subject.value=data.subject;subject.setAttribute('aria-label','Email subject');
            const text=document.createElement('textarea');text.readOnly=true;text.value=data.text;text.rows=14;text.style.width='100%';text.setAttribute('aria-label','Plain-text email body');
            const frame=document.createElement('iframe');frame.title='Formatted email body';frame.setAttribute('sandbox','');frame.style.width='100%';frame.style.height='360px';
            frame.srcdoc='<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'"></head><body>'+data.html+'</body></html>';
            const note=document.createElement('p');note.textContent='Preview and copy, then attach the downloaded HTML snapshot yourself. No email is sent. Share only with authorized recipients.';
            const controls=document.createElement('div');controls.className='actions';
            const result=document.createElement('p');result.setAttribute('role','status');
            for(const [label,copy] of [['Copy subject',()=>navigator.clipboard.writeText(data.subject)],['Copy plain text',()=>navigator.clipboard.writeText(data.text)],['Copy formatted body',async()=>{
                if(!navigator.clipboard?.write||typeof ClipboardItem==='undefined')throw Error('Formatted copying is unavailable in this browser. Use the plain-text body below.');
                await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([data.html],{type:'text/html'}),'text/plain':new Blob([data.text],{type:'text/plain'})})]);
            }]]){
                const button=document.createElement('button');button.type='button';button.textContent=label;
                button.onclick=async()=>{try{await copy();result.textContent='Copied.';}catch(error){result.textContent=error.message+' You can select and copy the subject/plain text manually.';}};controls.append(button);
            }
            const close=document.createElement('button');close.type='button';close.textContent='Close preview';close.onclick=()=>{emailPanel.replaceChildren();emailPanel.hidden=true;};controls.append(close);
            emailPanel.replaceChildren(title,note,subject,controls,result,frame,text);emailPanel.hidden=false;emailPanel.scrollIntoView({block:'nearest'});
        }
        let enabled=false;
        async function load(){
            const data=await request();enabled=data.enabled;toggle.textContent=enabled?'Disable scheduled captures':'Enable scheduled captures';
            selected.clear();updateSelection();
            status.textContent=`${data.emailStatus} Worker last seen: ${data.heartbeat?new Date(data.heartbeat).toLocaleString():'not yet connected'}.`;
            const table=document.createElement('table'),thead=document.createElement('thead'),header=document.createElement('tr');
            const selectHeader=document.createElement('th'),all=document.createElement('input');all.type='checkbox';all.setAttribute('aria-label','Select all deletable snapshots');selectHeader.append(all);header.append(selectHeader);
            all.onchange=()=>{for(const box of list.querySelectorAll('input[data-report-id]')){box.checked=all.checked;if(box.checked)selected.add(box.dataset.reportId);else selected.delete(box.dataset.reportId);}updateSelection();};
            ['Scheduled cutoff (Jamaica)','Captured at (Jamaica)','State','Details','Reports'].forEach(text=>{const th=document.createElement('th');th.textContent=text;header.append(th);});thead.append(header);table.append(thead);
            const tbody=document.createElement('tbody');
            for(const report of data.reports){
                const row=document.createElement('tr');
                const selection=document.createElement('td');
                if(report.state!=='running'){
                    const box=document.createElement('input');box.type='checkbox';box.dataset.reportId=report.id;box.setAttribute('aria-label',`Select snapshot ${report.cutoff}`);
                    box.onchange=()=>{if(box.checked)selected.add(report.id);else selected.delete(report.id);all.checked=false;updateSelection();};selection.append(box);
                }
                row.append(selection);
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
                    const email=document.createElement('button');email.type='button';email.textContent='Generate email body';
                    email.onclick=()=>void action(()=>showEmail(report.id));links.append(email);
                }
                row.append(td);tbody.append(row);
            }
            if(!data.reports.length){const row=document.createElement('tr'),td=document.createElement('td');td.colSpan=6;td.textContent='No snapshots captured yet.';row.append(td);tbody.append(row);}
            table.append(tbody);list.replaceChildren(table);
        }
        async function action(fn){
            if(busy)return;busy=true;capture.disabled=refresh.disabled=toggle.disabled=true;updateSelection();
            try{await fn();}catch(error){status.textContent=error.message;}finally{busy=false;capture.disabled=refresh.disabled=toggle.disabled=false;updateSelection();}
        }
        capture.onclick=()=>void action(async()=>{status.textContent='Refreshing source and capturing snapshot...';await request('POST',{});await load();});
        refresh.onclick=()=>void action(load);
        toggle.onclick=()=>void action(async()=>{await request('PUT',{enabled:!enabled});await load();});
        remove.onclick=()=>{
            const ids=[...selected];
            if(!ids.length||!window.confirm(`Permanently delete ${ids.length} selected snapshot(s), including HTML, XLSX and saved history? Attendance/schedules are unchanged. Downloaded or emailed copies cannot be recalled. Scheduled cutoffs will not regenerate.`))return;
            void action(async()=>{await request('DELETE',{ids,confirm:true});emailPanel.replaceChildren();emailPanel.hidden=true;await load();status.textContent=`Deleted ${ids.length} snapshot(s).`;});
        };
        try{await load();}catch(error){status.textContent=error.message;capture.disabled=toggle.disabled=true;}
    }
    new MutationObserver(()=>{
        const node=document.getElementById('attendanceReports');
        if(node&&node!==active)void mount(node);
        else if(!node)active=null;
        mountTableDownloads();
    }).observe(document.body,{childList:true,subtree:true});
})();
