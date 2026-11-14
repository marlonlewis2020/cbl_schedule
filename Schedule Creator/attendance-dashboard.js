(function(){
    "use strict";
    let liveDashboardExpanded=true;

    const node=(tag,text,className)=>{
        const value=document.createElement(tag);
        if(text!==undefined)value.textContent=text;
        if(className)value.className=className;
        return value;
    };
    const count=value=>Number(value||0).toLocaleString();
    const percent=value=>value===null||value===undefined?"N/A":`${Number(value).toFixed(1)}%`;
    document.addEventListener("toggle",event=>{
        if(event.target?.dataset?.dashboardDisclosure==="true")liveDashboardExpanded=event.target.open;
    },true);

    window.renderLiveAttendanceDashboard=function(target,data,audience,error,filters={}){
        if(!target)return;
        const wasOpen=target.querySelector("details[data-dashboard-disclosure]")?.open??liveDashboardExpanded;
        liveDashboardExpanded=wasOpen;
        target.classList.add("panel","collapsible");
        target.replaceChildren();
        const details=node("details"),summary=node("summary"),content=node("div",undefined,"panel-body");
        details.dataset.dashboardDisclosure="true";details.open=wasOpen;
        summary.append(node("h2","Live attendance dashboard"));
        details.append(summary,content);target.append(details);
        if(error){
            content.append(node("p",error,"attendance-dashboard-error"));
            return;
        }
        if(!data){
            content.append(node("p","Waiting for attendance data.","note"));
            return;
        }
        const reportDate=data.date||"Unavailable";
        content.append(node("p",`${reportDate} · Reported ${data.reportedAt||"Unavailable"} · ${data.timezone||"America/Jamaica"} · Source: ${data.shiftSource||"Unavailable"}`,"attendance-dashboard-meta"));
        if(data.lastSyncedAt)content.append(node("p",`Source refreshed ${data.lastSyncedAt}`,"note"));

        const allLocationGroups=Array.isArray(data.locations)?data.locations:[];
        const locationGroups=allLocationGroups.filter(location=>!filters.location||filters.location==="All"||location.location===filters.location);
        for(const location of locationGroups){
            location.visibleRoles=(location.roles||[]).filter(role=>!filters.role||filters.role==="All"||role.role===filters.role);
        }
        const metrics={...(data.summary||{})};
        if(audience==="admin"&&(filters.location&&filters.location!=="All"||filters.role&&filters.role!=="All")){
            for(const key of ["expected","actual","clockedIn","late","absent","approvedLeave","sick","vacation","currentShifts","openClocks","missingClockIns","earlyDepartures","overtimeMinutes"])metrics[key]=0;
            for(const location of locationGroups)for(const role of location.visibleRoles)for(const key of Object.keys(metrics))if(key!=="attendancePercent"&&key!=="exceptionCount")metrics[key]+=Number(role.summary?.[key]||0);
            metrics.attendancePercent=metrics.expected?Math.round(10000*metrics.actual/metrics.expected)/100:null;
            metrics.exceptionCount=(Array.isArray(data.exceptions)?data.exceptions:[]).filter(item=>(!filters.location||filters.location==="All"||item.location===filters.location)&&(!filters.role||filters.role==="All"||item.role===filters.role)).length;
        }
        const cards=node("div",undefined,"attendance-dashboard-kpis");
        for(const [label,value] of [
            ["Expected shifts",count(metrics.expected)],
            ["Clock-in evidence",count(metrics.clockedIn)],
            ["On shift now",count(metrics.currentShifts)],
            ["Open clock entries",count(metrics.openClocks)],
            ["Attendance",percent(metrics.attendancePercent)],
            ["Late / absent",`${count(metrics.late)} / ${count(metrics.absent)}`],
            ["Leave / sick / vacation",`${count(metrics.approvedLeave)} / ${count(metrics.sick)} / ${count(metrics.vacation)}`],
        ]){
            const item=node("div",undefined,"attendance-dashboard-kpi");
            if(label==="On shift now")item.title="Shifts in progress with one matching open clock entry.";
            if(label==="Open clock entries")item.title="Shifts with a clock-in recorded and no clock-out; some may no longer be current.";
            item.append(node("span",label),node("strong",value));
            cards.append(item);
        }
        content.append(cards);

        if(audience==="employee"){
            const team=node("section",undefined,"attendance-dashboard-team");
            for(const location of locationGroups){
                team.append(node("h3",`My team · ${location.location} × ${location.visibleRoles.map(role=>role.role).join(", ")||"Your role"}`));
                for(const role of location.visibleRoles){
                    team.append(node("h4",`Shift breakdown · ${location.location} × ${role.role}`));
                    const table=node("table"),head=table.createTHead().insertRow();
                    for(const label of ["Shift start","Expected","Clocked in","Attendance","Late","Absent","Leave"]){head.append(node("th",label));}
                    const body=table.createTBody();
                    for(const shift of role.shifts||[]){
                        const row=body.insertRow(),summary=shift.summary;
                        for(const value of [shift.shiftStart,count(summary.expected),count(summary.clockedIn),percent(summary.attendancePercent),count(summary.late),count(summary.absent),count(summary.approvedLeave)])row.append(node("td",value));
                    }
                    if(!role.shifts?.length){const row=table.createTBody().insertRow(),cell=node("td","No shifts have started.");cell.colSpan=7;row.append(cell);}
                    team.append(table);
                }
            }
            if(!locationGroups.length)team.append(node("p","No team shifts have started for this date.","note"));
            content.append(team);
            return;
        }

        const breakdown=node("section",undefined,"attendance-dashboard-breakdown");
        breakdown.append(node("h3","Location → role → shift"));
        for(const location of locationGroups){
            let locationSummary=location.summary||{};
            if(audience==="admin"&&filters.role&&filters.role!=="All"){
                locationSummary={expected:0,actual:0,clockedIn:0,late:0,absent:0,approvedLeave:0,attendancePercent:null};
                for(const role of location.visibleRoles)for(const key of ["expected","actual","clockedIn","late","absent","approvedLeave"])locationSummary[key]+=Number(role.summary?.[key]||0);
                locationSummary.attendancePercent=locationSummary.expected?Math.round(10000*locationSummary.actual/locationSummary.expected)/100:null;
            }
            breakdown.append(node("h4",`${location.location} · ${count(locationSummary.clockedIn)} clocked in of ${count(locationSummary.expected)} expected · ${percent(locationSummary.attendancePercent)}`));
            if(audience==="admin"&&filters.role&&filters.role!=="All"&&!location.visibleRoles.length){
                breakdown.append(node("p",`No ${filters.role} role/team at this location.`));
            }
            for(const role of location.visibleRoles){
                const roleSummary=role.summary||{};
                breakdown.append(node("h5",`${role.role} · ${count(roleSummary.clockedIn)} / ${count(roleSummary.expected)} · ${percent(roleSummary.attendancePercent)}`));
                breakdown.append(node("h6",`Team · ${location.location} × ${role.role}`));
                const table=node("table"),head=table.createTHead().insertRow();
                for(const label of ["Shift start","Expected","Clocked in","Attendance","Late","Absent","Leave"]){head.append(node("th",label));}
                const body=table.createTBody();
                for(const shift of role.shifts||[]){
                    const row=body.insertRow(),summary=shift.summary;
                    for(const value of [shift.shiftStart,count(summary.expected),count(summary.clockedIn),percent(summary.attendancePercent),count(summary.late),count(summary.absent),count(summary.approvedLeave)])row.append(node("td",value));
                }
                if(!role.shifts?.length){const row=table.createTBody().insertRow(),cell=node("td","No shifts have started.");cell.colSpan=7;row.append(cell);}
                breakdown.append(table);
            }
        }
        if(!locationGroups.length)breakdown.append(node("p","No shifts have started for this date.","note"));
        content.append(breakdown);

        const exceptions=(Array.isArray(data.exceptions)?data.exceptions:[]).filter(item=>
            (!filters.location||filters.location==="All"||item.location===filters.location)&&
            (!filters.role||filters.role==="All"||item.role===filters.role));
        const section=node("section",undefined,"attendance-dashboard-exceptions");
        section.append(node("h3",`Exceptions · ${count(metrics.exceptionCount)}`));
        if(!exceptions.length){
            section.append(node("p","No late arrivals, absences, missing clock-ins, early departures or overtime recorded.","note"));
        }else{
            const table=node("table"),head=table.createTHead().insertRow();
            for(const label of ["Employee","Location","Role","Shift start","Status","Reason"]){head.append(node("th",label));}
            const body=table.createTBody();
            for(const item of exceptions){
                const row=body.insertRow();
                for(const value of [item.name||item.employeeId,item.location,item.role,item.shiftStart,item.status,item.reason])row.append(node("td",value||""));
            }
            section.append(table);
        }
        content.append(section);
    };
})();
