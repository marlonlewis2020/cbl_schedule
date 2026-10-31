window.CBL_STORAGE_BRIDGE=function(){
    const browserRecordStore=store;
    let serverWorkspaceVersion=0,serverSaveQueue=Promise.resolve();
    store=function(action,value,recordKey='current'){
        if(recordKey!=='current')return browserRecordStore(action,value,recordKey);
        initLocalConnector();
        const perform=async()=>{
            let response=await fetch('/api/workspace',{
                method:action==='put'?'PUT':'GET',
                headers:{
                    'Content-Type':'application/json',
                    'X-CBL-Connector-Token':localConnectorToken
                },
                cache:'no-store',
                ...(action==='put'?{
                    body:JSON.stringify({
                        model:value,version:serverWorkspaceVersion
                    })
                }
                :{})
            }),data=await response.json();
            if(!response.ok)throw Error(data.error||'Python workspace service unavailable');
            serverWorkspaceVersion=data.version;
            return action==='get'?data.model:undefined
        };
        if(action==='get')return perform();
        value=JSON.parse(JSON.stringify(value));
        let task=serverSaveQueue.then(perform);
        serverSaveQueue=task.catch(()=>{});
        return task
    };
    persistWorkspace=async function(value){
        await store('put',value);
        storageMode='persistent';
        storageStatus();
        return true
    };
    storageStatus=function(){
        let warning=$('storageWarning');
        if(warning)warning.hidden=true;
        $('savedState').textContent='Python web app · workspace saved on this computer · revision '+serverWorkspaceVersion;
        updateHeaderNotices()
    };
    init=async function(){
        try{
            initLocalConnector();
            let saved=await store('get');
            if(saved)model=migrateScheduleWeeks(saved);
            else{
                let encoded=atob($('payload').textContent.trim());
                model=migrateScheduleWeeks(JSON.parse(new TextDecoder().decode(await inflate(Uint8Array.from(encoded,c=>c.charCodeAt(0)),'gzip'))));
                await store('put',model)
            }
            storageMode='persistent';
            await loadBambooCredentials();
            render()
        }
        catch(error){
            $('content').innerHTML='<div class="empty"><h2>Workspace could not be opened</h2><p>'+esc(error.message)+'</p><p>Reopen the full session URL printed by the Python launcher. Existing saved data has not been replaced.</p></div>'
        }
    };
    const standalonePortableHtmlBlob=portableHtmlBlob;
    portableHtmlBlob=async function(){
        let blob=await standalonePortableHtmlBlob(),html=await blob.text();
        html=html.replace('<script src="server-storage-v2.js"></script>','');
        return new Blob([html],{type:'text/html'})
    }
};
