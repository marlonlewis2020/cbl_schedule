function runLiveAttendanceDashboardTests() {
    const target=document.getElementById("dashboardFixture");
    const metrics={expected:2,actual:1,clockedIn:1,attendancePercent:50,exceptionCount:1};
    const longName="LongEmployeeIdentifier".repeat(12);
    const data={date:"2026-11-18",summary:metrics,locations:["Kingston","St Ann"].map(location=>({
        location,summary:metrics,roles:[{role:"Cashier",summary:metrics,shifts:[{shiftStart:"08:00",summary:metrics}]}],
    })),exceptions:[{name:longName,location:"Kingston",role:"Cashier",shiftStart:"08:00",status:"late",reason:"Late arrival"}]};
    let passed=0;
    const check=(condition,label)=>{if(!condition)throw Error(label);passed++;};
    for(const audience of ["admin","manager","employee"]){
        const view=audience==="admin"?data:{...data,locations:[data.locations[0]]};
        window.renderLiveAttendanceDashboard(target,view,audience,null,audience==="admin"?{location:"Kingston",role:"Cashier"}:{});
        check(target.textContent.includes("Kingston")&&!target.textContent.includes("St Ann"),`${audience} displays the selected/scoped location`);
        check(target.textContent.includes(longName)===(audience!=="employee"),`${audience} exception visibility`);
        const regions=[...target.querySelectorAll('[role="region"]')];
        check(regions.length===(audience==="employee"?1:2)&&regions.every(region=>region.tabIndex===0&&region.getAttribute("aria-label")&&region.querySelector("th[scope=col]")),`${audience} tables have named keyboard-accessible scroll regions`);
        check(document.documentElement.scrollWidth<=document.documentElement.clientWidth,`${audience} dashboard fits the viewport without page-level scrolling`);
    }
    return {passed};
}

async function runEmployeeDashboardRefreshTests(source) {
    const requests=[];
    const elements={teamSummary:{},teamDashboardGroups:{}};
    const calls=[];
    const api=async path=>{
        requests.push(path);
        if(requests.length===1)return {date:"2026-11-18",present:1,expected:2,counts:{late:1}};
        throw Error("Dashboard unavailable");
    };
    const load=new Function("$","api","clockLabel","window",
        source.slice(source.indexOf("async function loadTeamAttendance()"),source.indexOf("async function api("))+"; return loadTeamAttendance;")(
        selector=>elements[selector.slice(1)],api,()=>"08:00",{renderLiveAttendanceDashboard:(...args)=>calls.push(args)});
    await load();
    if(!elements.teamSummary.textContent.includes("1 present of 2")||calls.length!==1||calls[0][1]!==null||calls[0][3]!=="Dashboard unavailable"){
        throw Error("A failed detailed dashboard request must replace stale detail with its error while retaining the fresh team summary.");
    }
    return {passed:1};
}
