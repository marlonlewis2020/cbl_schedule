async function runSavedRegisterTests(source) {
    new Function(source);
    const slice=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end));
    let checks=0,confirmDelete=false,deny=false,failStorage=false,posts=0;
    const assert=(value,label)=>{if(!value)throw Error(label);checks++;};
    const runs=Array.from({length:9},(_,i)=>({id:'run-'+i,start:'2026-11-09',end:'2026-11-15',location:'Location '+i,
        role:i===2?'Long role label '.repeat(15):'Cashier',revision:1,primary:5,makeup:0,uncovered:[],shortages:[]}));
    const initial={results:runs,selectedRun:'run-0',previousScheduleSet:{results:runs},user:{email:'test@example.test'}};
    const definitions=slice("function visibleScheduleRuns(){","function scheduleFilters(){")+
        slice("let scheduleRegisterObserver=","function rebuildScheduleAudit(")+
        slice("function savedScheduleRegister(","function runView(")+
        slice("function store(","function storageStatus(");
    const factory=new Function('$','panel','esc','sum','directoryRequest','confirm','document','failStorage',
        `let model=${JSON.stringify(initial)},storageMode='persistent',tenantAuthCsrfToken='token',saveTimer,
        preparedEmailGeneration=0,preparedEmail={old:true},scheduleLocation='All',scheduleRole='All',
        scheduleWeek='All',scheduleOrigin='All';
        const realStore=async(...args)=>{if(failStorage())throw Error('Storage unavailable');return store(...args)};
        function render(){document.querySelector('#fixture').innerHTML=savedScheduleRegister(visibleScheduleRuns());sizeScheduleRegister();}
        function message(){}
        ${definitions.replace("await store('put',next)","await realStore('put',next)")}
        tenantAuthTenantId='tenant-test';
        return {render,remove:deleteSavedSchedule,model:()=>model,
            persist:()=>store('put',model),reload:async()=>{model=await store('get');render();},
            filter:()=>{scheduleLocation='Location 0';scheduleRole='Cashier';},
            filters:()=>({scheduleLocation,scheduleRole}),email:()=>preparedEmail,observer:()=>scheduleRegisterObserver};`
    );
    document.body.innerHTML='<main id="fixture"></main>';
    const functions=factory(
            id=>document.getElementById(id),(title,html)=>html,
            text=>String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
            values=>values.reduce((a,b)=>a+b,0),
            async()=>{posts++;if(deny)throw Error('Sign in required');return {authorized:true};},
            ()=>confirmDelete,document,()=>failStorage
    );
    try {
        await functions.persist();functions.render();
        await new Promise(resolve=>requestAnimationFrame(resolve));
        let wrapper=document.getElementById('savedScheduleRegister'),table=wrapper.querySelector('table');
        let rows=[...table.tBodies[0].rows];
        const action=rows[0].querySelector('[data-action="deleteSavedSchedule"]'),actionStyle=getComputedStyle(action);
        assert(action.parentElement.matches('.actions.employee-actions.attendance-actions')&&
            actionStyle.minHeight==='40px'&&actionStyle.borderRadius==='8px'&&
            actionStyle.backgroundColor==='rgb(180, 67, 43)',
            'Register actions reuse attendance button sizing and retain destructive styling');
        const six=rows[5].getBoundingClientRect().bottom-table.getBoundingClientRect().top;
        assert(wrapper.clientHeight<=six+1&&wrapper.scrollHeight>wrapper.clientHeight,'Viewport fits at most six variable-height rows');
        assert(wrapper.tabIndex===0&&getComputedStyle(table.tHead.rows[0].cells[0]).position==='sticky','Keyboard region and sticky header');
        const header=table.tHead.rows[0].cells[0],background=getComputedStyle(header).backgroundColor;
        assert(background===(document.documentElement.dataset.theme==='dark'?'rgb(32, 57, 70)':'rgb(242, 247, 249)'),'Header retains theme contrast');
        wrapper.focus();
        assert(document.activeElement===wrapper,'Scrolling region accepts keyboard focus');
        wrapper.scrollTop=wrapper.scrollHeight;
        assert(Math.abs(header.getBoundingClientRect().top-wrapper.getBoundingClientRect().top)<=2,'Header remains visible while scrolling');
        wrapper.scrollTop=0;
        await functions.remove('run-0');
        assert(functions.model().results.length===9&&posts===0,'Cancel leaves workspace and authorization untouched');
        confirmDelete=true;deny=true;
        try{await functions.remove('run-0');}catch(error){assert(error.message==='Sign in required','Server denies unauthorized deletion');}
        assert(functions.model().results.length===9,'Authorization failure preserves schedule');
        deny=false;failStorage=true;
        try{await functions.remove('run-0');}catch(error){assert(error.message.includes('not deleted'),'Storage failure explicitly reported');}
        assert(functions.model().results.length===9,'Storage failure preserves in-memory schedule');
        failStorage=false;functions.filter();
        await functions.remove('run-0');
        assert(functions.model().results.length===8&&!functions.model().results.some(r=>r.id==='run-0'),'Only requested workspace schedule deleted');
        assert(functions.model().previousScheduleSet===null&&functions.model().scheduleDeletionHistory.length===1,'Undo cannot restore deletion; audit retained');
        assert(functions.model().selectedRun==='run-1'&&functions.email()===null,'Selected schedule replaced and stale email preparation cleared');
        assert(functions.filters().scheduleLocation==='All','Obsolete location filter cleared');
        await functions.reload();
        assert(functions.model().results.length===8&&!functions.model().results.some(r=>r.id==='run-0'),'IndexedDB reload preserves deletion');
        for(let i=1;i<6;i++)await functions.remove('run-'+i);
        wrapper=document.getElementById('savedScheduleRegister');
        assert(functions.model().results.length===3&&wrapper.style.maxHeight==='none','Short register has no six-row blank space');
        for(let i=6;i<9;i++)await functions.remove('run-'+i);
        await functions.reload();
        assert(functions.model().results.length===0&&functions.model().selectedRun==='','Deleting last record persists an empty register/selection');
        return {passed:checks};
    } finally { functions.observer()?.disconnect(); }
}
