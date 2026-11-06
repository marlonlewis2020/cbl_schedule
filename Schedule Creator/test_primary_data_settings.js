async function runPrimaryDataSettingsTests(source) {
    new Function(source);
    const slice=(start,end)=>{
        const from=source.indexOf(start),to=source.indexOf(end,from);
        if(from<0||to<0)throw Error('Missing production test boundary: '+start);
        return source.slice(from,to);
    };
    let checks=0,denied=false,wrongTenant=false,downloads=0,reads=0,requests=[];
    const assert=(value,label)=>{if(!value)throw Error(label);checks++;};
    document.body.innerHTML='<nav id="appMenu"><div class="nav-group"><button data-page="source">Source</button></div><div class="nav-group"><button data-page="schedules">Schedules</button><button data-page="settings">Settings</button></div></nav><main id="content"></main><dialog id="sourcePickerDialog"></dialog><dialog id="sourceImportReviewDialog"></dialog>';
    const factory=new Function('request','download','read',`
        let model={settings:{menus:{}},sourceName:'Test source',results:[],locked:false,
            locations:[{open:[1,1,1,1,1,0,0],intensity:[.2,.2,.2,.2,.2,0,0]}]},page='settings',
            tenantAuthPrimaryAdmin=false,tenantAuthTenantId='business',tenantAuthCsrfToken='csrf',
            pendingSourceImport=null,busy=false,storageMode='persistent',lastMessage='';
        const $=id=>document.getElementById(id);
        const esc=value=>String(value);
        const heading=()=>'';
        const businessSettingsPanel=()=>'<section class="panel" id="businessSettings">Business settings</section>';
        const accessAccountsPanel=()=>'';
        const overtimeSettingsPanel=()=>'';
        const initNavGroups=()=>{};
        const closeAppMenu=()=>{};
        const loadAccessAccounts=()=>{};
        const updateMicrosoftConfigNotice=()=>{};
        const directoryRequest=request;
        const downloadFile=download;
        const message=text=>{lastMessage=text;};
        const setSharePointStatus=message;
        const migrateScheduleWeeks=value=>value;
        const overtimeIssues=()=>[];
        const validateRun=()=>[];
        const persistWorkspace=async()=>{};
        const workbookBlob=()=>new Blob(['inputs']);
        const inputTables=()=>[];
        const queueSave=()=>{};
        const refreshConfigurationIndicators=()=>{};
        let filterLoc='All',filterRole='All';
        ${slice("const MENU_GROUPS=","let businessConfig=")}
        ${slice("function pageAllowed(","function attendanceSortHeader(")}
        ${slice("function panel(","function collapsiblePanel(")}
        ${slice("function applyMenuSettings(","function jamaicaDate(")}
        ${slice("async function authorizeDataSettings(","function sizeScheduleRegister(")}
        ${slice("async function nav(","function closeAppMenu(")}
        ${slice("async function openSourcePicker(","function setSharePointStatus(")}
        ${slice("async function importSourceFile(","async function restoreWorkspace(")}
        ${slice("async function restoreWorkspace(","async function portableHtmlBlob(")}
        ${slice("async function downloadInputs(","const MENU_GROUPS=")}
        ${slice("async function portableBundleFiles(","async function portable(")}
        ${slice("async function approveSourceImportMappings(","function scheduleLocationsPage(")}
        ${slice("async function updateMetaSetting(","function editChange(")}
        ${slice("function store(","function storageStatus(")}
        ${slice("async function action(","function store(")}
        function render(){
            $('content').innerHTML=settingsPage();
            applyMenuSettings();
        }
        return {render,allowed:pageAllowed,nav,action,inputs:downloadInputs,
            picker:openSourcePicker,importFile:importSourceFile,restore:restoreWorkspace,
            bundle:portableBundleFiles,approve:approveSourceImportMappings,
            updateMeta:updateMetaSetting,
            reload:async()=>{await store('put',model,'meta-permission-test');model=await store('get',undefined,'meta-permission-test');},
            setPrimary:value=>{tenantAuthPrimaryAdmin=value;},
            setSourcePreference:value=>{model.settings.menus.source=value;},
            page:()=>page,message:()=>lastMessage,model:()=>model,
            pending:value=>{pendingSourceImport=value;},getPending:()=>pendingSourceImport};
    `);
    const app=factory(async(path,options={})=>{
        requests.push({path,options});
        if(denied)throw Error('Primary administrator required');
        return {authorized:true,tenantId:wrongTenant?'other':'business'};
    },()=>downloads++,()=>reads++);
    app.render();
    assert(!app.allowed('source')&&app.allowed('settings')&&app.allowed('schedules')&&!app.allowed('meta'),'Additional admin keeps scheduling and Settings, not Source or META');
    assert(document.querySelector('[data-page="source"]').hidden&&document.querySelector('[data-page="source"]').parentElement.hidden,'Restricted page and empty navigation group hidden');
    assert(document.querySelector('[data-action="sourcePicker"]').closest('.panel').hidden&&
        document.querySelector('[data-action="portable"]').closest('.panel').hidden,'Duplicate Settings import and backup panels hidden');
    assert(!document.querySelector('[data-action="portable"]').checkVisibility(),'Restricted Settings action not visually displayed');
    assert(!document.getElementById('businessSettings').hidden,'Separate business Settings panel retained');
    assert(document.querySelector('[data-menu-setting="source"]').disabled,'Menu preferences cannot grant primary permission');
    app.setPrimary(true);app.render();
    assert(app.allowed('source')&&!document.querySelector('[data-page="source"]').hidden,'Primary admin sees Data & Settings');
    assert(!document.querySelector('[data-action="portable"]').closest('.panel').hidden,'Primary admin retains portable export');
    const meta={dataset:{meta:'0',day:'0',field:'intensity'},value:'35'};
    await app.updateMeta(meta);
    assert(app.model().locations[0].intensity[0]===.35&&JSON.parse(requests.at(-1).options.body).operation==='meta-update','META edits require fresh authorization and preserve percentage conversion');
    const before=JSON.stringify(app.model().locations);
    app.model().locked=true;
    await app.updateMeta({...meta,value:'45'});
    assert(JSON.stringify(app.model().locations)===before,'Locked META remains unchanged');
    app.model().locked=false;
    await app.updateMeta({dataset:{meta:'0',day:'6',field:'open'},checked:true});
    assert(app.model().locations[0].open[6]===1,'Operating-day toggle retains numeric representation');
    await app.reload();
    assert(app.model().locations[0].intensity[0]===.35&&app.model().locations[0].open[6]===1,'META values preserved after IndexedDB round trip');
    await app.updateMeta({dataset:{meta:'0',day:'6',field:'open'},checked:false});
    await app.nav('meta');
    assert(app.page()==='meta','Primary admin can navigate directly to META');
    await app.inputs();
    assert(downloads===1&&JSON.parse(requests.at(-1).options.body).operation==='configured-inputs','Configured-input export requires server authorization');
    await app.action('backup');
    assert(downloads===2&&JSON.parse(requests.at(-1).options.body).operation==='backup','Backup export requires server authorization');
    assert(requests.at(-1).options.headers['X-CSRF-Token']==='csrf','Protected requests include CSRF token');
    await app.nav('source');
    assert(app.page()==='source','Primary source navigation authorized');
    denied=true;app.pending({test:true});
    await app.updateMeta({...meta,value:'45'});
    assert(JSON.stringify(app.model().locations)===before,'Revoked META edit preserves calendars');
    await app.nav('source');
    assert(app.page()==='controls'&&!app.allowed('source')&&app.getPending()===null,'Revoked permission removes protected view and pending import');
    assert(app.message().includes('Primary administrator'),'Denied navigation reports server error');
    app.setPrimary(true);
    try{await app.inputs();}catch(error){assert(error.message.includes('Primary administrator'),'Direct export denial surfaced');}
    assert(downloads===2,'Revoked export produces no file');
    app.setPrimary(true);
    try{await app.bundle();}catch(error){assert(error.message.includes('Primary administrator'),'Portable bundle fails before fetching assets');}
    app.setPrimary(true);
    try{await app.approve();}catch(error){assert(error.message.includes('Primary administrator'),'Mapping approval rechecks permission before mutation');}
    app.setPrimary(true);
    await app.picker();
    assert(!document.getElementById('sourcePickerDialog').open,'Revoked source picker cannot open');
    app.setPrimary(true);
    await app.action('sharePointConnect');
    assert(app.message().includes('Primary administrator'),'SharePoint actions recheck permission before contacting Microsoft');
    app.setPrimary(true);
    await app.importFile({arrayBuffer:async()=>{reads++;return new ArrayBuffer(0);}});
    assert(reads===0&&app.message().includes('Import failed'),'Denied source import does not read or replace workspace');
    app.setPrimary(true);
    await app.restore({target:{files:[{text:async()=>{reads++;return '{}';}}],value:'backup'}});
    assert(reads===0&&app.message().includes('Restore failed'),'Denied restore does not read or replace workspace');
    app.setPrimary(true);denied=false;wrongTenant=true;
    await app.nav('source');
    assert(!app.allowed('source')&&app.message().includes('changed'),'Tenant change fails closed');
    wrongTenant=false;app.setPrimary(true);app.setSourcePreference(false);app.render();
    assert(!app.allowed('source')&&app.allowed('settings'),'Existing menu preference still applies for primary admin');
    return {passed:checks};
}
