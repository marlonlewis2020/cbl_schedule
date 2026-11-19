async function runAttendanceFilterLoadingTests(source, reports, dialogMarkup) {
    document.body.insertAdjacentHTML('beforeend', `<main id="content"></main>${dialogMarkup}`);
    const $ = id => document.getElementById(id);
    const requests = [], downloads = [];
    const api = path => new Promise((resolve, reject) => requests.push({path, resolve, reject}));
    window.fetch = async () => new Response('{"reports":[],"settings":{}}', {status: 200});
    window.workbookBlob = async sheets => sheets;
    window.downloadFile = (name, sheets) => downloads.push({name, sheets});
    new Function(reports)();
    const slice = (from, to) => source.slice(source.indexOf(from), source.indexOf(to, source.indexOf(from)));
    const fixture = new Function('$', 'directoryRequest', `
        const page='attendance', model={}, scheduleLocations=[{location:'Kingston',roleGroup:'Cashier'},{location:'St Ann',roleGroup:'Cashier'}];
        const membershipFeatureEnabled=()=>false;
        const esc=value=>String(value??'');
        const heading=(name)=>'<h1>'+name+'</h1>';
        const panel=(name,body)=>'<section class="panel"><h3>'+name+'</h3>'+body+'</section>';
        const collapsiblePanel=(id,name,body)=>panel(name,body);
        const select=(options,current,attrs)=>'<select '+attrs+'>'+options.map(([value,label])=>'<option value="'+value+'" '+(value===current?'selected':'')+'>'+label+'</option>').join('')+'</select>';
        const stats=rows=>'<section id="testTotals">'+rows.map(([name,value])=>'<p>'+name+': '+value+'</p>').join('')+'</section>';
        const f=value=>String(value),badge=value=>String(value);
        const attendanceSort={shifts:{},scores:{}};
        let attendanceLoadSequence=0,attendanceDashboardData,attendanceDashboardError,attendanceSyncStatus='';
        let attendanceLocationFilter='Kingston',attendanceRoleFilter='All',attendancePeriodMode='day';
        let attendanceSelectedDate='2026-11-18',attendanceStartMonth='2026-11',attendanceEndMonth='2026-11';
        const makeData=(shifts,date='2026-11-18')=>({date,currentDate:'2026-11-18',periodStart:date,periodEnd:date,
            shifts:shifts.map(([location,name])=>({location,name,date,role:'Cashier',status:'attended',shiftStart:date+'T08:00:00-05:00'})),scores:[]});
        let attendanceData=makeData([['Kingston','Kingston employee'],['St Ann','St Ann employee']]);
        const render=()=>$('content').innerHTML=attendancePage();
        ${slice('const attendanceFilterFields=', 'const $=')}
        ${slice('function attendanceSortHeader(', 'function openAttendanceClockActionDialog(')}
        ${slice('function attendanceFilterSelection(', 'async function syncAttendance(')}
        ${slice("document.addEventListener('change',e=>{", "document.addEventListener('input',e=>{")}
        const retry=async a=>{${slice("if(a==='retryAttendanceFilters'", "if(['backup','restore','sourceInputs'")}};
        $('content').addEventListener('click', event=>retry(event.target.dataset.action));
        render();
        return {makeData};
    `)($, api);
    const wait = () => new Promise(resolve => setTimeout(resolve, 0));
    const choose = (id, value) => {
        const input = $(id);
        input.value = value;
        input.dispatchEvent(new Event('change', {bubbles:true}));
    };
    const exportButton = () => $('content').querySelector('[aria-label^="Download Excel: Attendance ·"]');
    let passed = 0;
    const check = (condition, label) => {if(!condition)throw Error(label);passed++;};
    await wait();
    choose('attendanceLocationFilter', 'St Ann');
    check($('attendanceFilterLoading').open && $('attendanceFilterLoading').textContent.includes('Please wait while attendance data updates.'), 'The filter opens the blocking spinner.');
    $('content').querySelector('[data-action="editAttendanceShift"]').focus();
    check(!$('content').contains(document.activeElement), 'Background controls cannot take focus during a refresh.');
    exportButton().click();
    await wait();
    check(!downloads.length && $('testTotals').textContent.includes('Expected shifts: 1'), 'Download is blocked and prior totals stay in place while loading.');
    requests.shift().reject(Error('Network unavailable'));
    await wait();
    check(!$('attendanceFilterLoading').open && $('attendanceDisplayedFilters').textContent.includes('Kingston')
        && $('content').querySelector('[role="alert"]').textContent.includes('St Ann'), 'Failure labels both the displayed and attempted filters.');
    exportButton().click();
    await wait();
    const saved = JSON.stringify(downloads[0].sheets.Attendance);
    check(saved.includes('Kingston employee') && !saved.includes('St Ann employee'), 'Failure exports only the still-visible Kingston rows.');
    $('content').querySelector('[data-action="retryAttendanceFilters"]').click();
    check(requests.length===1 && $('attendanceFilterLoading').open, 'Retry restarts the failed selection.');
    requests.shift().resolve(fixture.makeData([['St Ann','St Ann employee'],['St Ann','Second St Ann employee']]));
    await wait();
    check(!$('attendanceFilterLoading').open && $('attendanceDisplayedFilters').textContent.includes('St Ann')
        && $('testTotals').textContent.includes('Expected shifts: 2') && $('content').textContent.includes('Second St Ann employee')
        && !$('content').querySelector('[role="alert"]'), 'Retry applies the St Ann table and totals together.');
    choose('attendanceDateFilter', '2026-11-17');
    const request = requests.shift();
    check(request.path.endsWith('start=2026-11-17&end=2026-11-17'), 'Date changes request the selected period.');
    request.resolve(fixture.makeData([], '2026-11-17'));
    await wait();
    check(!$('attendanceFilterLoading').open && !$('content').hasAttribute('aria-busy')
        && $('attendanceLocationFilter').value==='St Ann' && $('content').textContent.includes('No attendance records')
        && $('testTotals').textContent.includes('Expected shifts: 0'), 'Empty results keep the requested filters, clear the totals and restore interaction.');
    exportButton().click();
    await wait();
    check(downloads[1].sheets.Attendance.length===1, 'An empty result does not export the empty-state message or old rows.');
    return {passed};
}
