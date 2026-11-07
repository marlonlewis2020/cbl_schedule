(()=>{
    "use strict";
    const mounted=new WeakSet();
    const endpointFor=mode=>mode==="manager"?"/api/access/manager/historical-reports":"/api/attendance/historical-reports";
    const jamaicaDate=()=>{
        const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"America/Jamaica",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
        const value=Object.fromEntries(parts.map(part=>[part.type,part.value]));
        return `${value.year}-${value.month}-${value.day}`;
    };
    const periodStart=(period,value)=>{
        if(!value)return "";
        const [year,month,day]=value.split("-").map(Number);
        if(period==="month")return `${year}-${String(month).padStart(2,"0")}-01`;
        const weekday=new Date(Date.UTC(year,month-1,day)).getUTCDay();
        const monday=new Date(Date.UTC(year,month-1,day-(weekday+6)%7));
        return `${monday.getUTCFullYear()}-${String(monday.getUTCMonth()+1).padStart(2,"0")}-${String(monday.getUTCDate()).padStart(2,"0")}`;
    };
    const element=(tag,content,className)=>{
        const node=document.createElement(tag);
        if(content!==undefined)node.textContent=content;
        if(className)node.className=className;
        return node;
    };
    async function fetchJson(url,options={}){
        const response=await fetch(url,{cache:"no-store",...options});
        const data=await response.json().catch(()=>({}));
        if(!response.ok)throw Error(data.error||"Historical attendance report request failed.");
        return data;
    }
    async function tokenFor(mode){
        const state=await fetchJson(mode==="manager"?"/api/access/state":"/api/tenant-auth/state");
        return state.csrfToken;
    }
    function link(parent,id,format,label,endpoint){
        const anchor=element("a",label);
        anchor.href=`${endpoint}/${encodeURIComponent(id)}/download?format=${format}`;
        anchor.setAttribute("download","");
        anchor.rel="noopener noreferrer";
        parent.append(anchor);
        return anchor;
    }
    function renderSummary(target,report,id,endpoint){
        target.replaceChildren();
        const title=element("h3",`${report.periodLabel}: ${report.start} to ${report.end}`);
        const detail=element("p",`Attendance score: ${report.summary.score===null?"Insufficient evidence":report.summary.score+"%"} · ${report.summary.present}/${report.summary.expected} eligible shifts · ${report.summary.lateDates} late date(s) · ${report.summary.absentDates} absent date(s).`);
        const compare=element("p",`Previous period ${report.comparison.start} to ${report.comparison.end}: ${report.comparison.previous.score===null?"Insufficient evidence":report.comparison.previous.score+"%"} · change ${report.comparison.change===null?"Insufficient evidence":`${report.comparison.change>0?"+":""}${report.comparison.change} pp`}.`);
        const links=element("div",undefined,"historical-report-links");
        link(links,id,"xlsx","Download Excel workbook",endpoint);
        links.append(document.createTextNode(" · "));
        link(links,id,"html","Download offline interactive HTML",endpoint);
        const evidence=element("p",report.evidence.dayOffPattern,"note");
        target.append(title,detail,compare,links,evidence);
    }
    function renderHistory(target,reports,endpoint){
        target.replaceChildren(element("h3","Saved historical reports"));
        if(!reports.length){
            target.append(element("p","No saved historical reports in your current authorized scope.","note"));
            return;
        }
        const table=element("table"),head=element("thead"),header=element("tr");
        ["Period","Dates","Saved","Filters","Downloads"].forEach(value=>header.append(element("th",value)));
        head.append(header);table.append(head);
        const body=element("tbody");
        for(const report of reports){
            const row=element("tr");
            row.append(element("td",report.period==="week"?"Weekly":"Monthly"));
            row.append(element("td",`${report.start} – ${report.end}`));
            row.append(element("td",report.createdAt));
            row.append(element("td",[report.location,report.role].filter(Boolean).join(" · ")||"All authorized teams"));
            const downloads=element("td");
            link(downloads,report.id,"xlsx","Excel",endpoint);
            downloads.append(document.createTextNode(" · "));
            link(downloads,report.id,"html","Offline HTML",endpoint);
            row.append(downloads);body.append(row);
        }
        table.append(body);
        const scroll=element("div",undefined,"scroll");
        scroll.append(table);target.append(scroll);
    }
    async function mount(container,mode){
        if(mounted.has(container))return;
        mounted.add(container);
        const endpoint=endpointFor(mode);
        const heading=element("h2","Historical attendance trend reports");
        const intro=element("p","Generate immutable weekly (Monday–Sunday) or calendar-month Excel and offline interactive HTML reports. Comparisons use the immediately preceding matching period; pattern analysis uses only the selected period and requires at least three eligible shifts.");
        const form=element("form",undefined,"historical-report-form");
        const periodLabel=element("label","Period");
        const period=document.createElement("select");
        period.name="period";period.required=true;
        for(const [value,label] of [["week","Weekly (Monday–Sunday)"],["month","Monthly"]]){
            const option=element("option",label);option.value=value;period.append(option);
        }
        periodLabel.append(period);
        const startLabel=element("label","Period start");
        const start=document.createElement("input");start.type="date";start.name="start";start.required=true;
        start.value=periodStart(period.value,jamaicaDate());startLabel.append(start);
        period.addEventListener("change",()=>{start.value=periodStart(period.value,start.value||jamaicaDate());});
        start.addEventListener("change",()=>{start.value=periodStart(period.value,start.value);});
        form.append(periodLabel,startLabel);
        if(mode==="admin"){
            const locationLabel=element("label","Distribution Centre");
            const location=document.createElement("select");location.name="location";
            const allLocations=element("option","All locations");allLocations.value="";location.append(allLocations);
            locationLabel.append(location);
            const roleLabel=element("label","Role");
            const role=document.createElement("select");role.name="role";
            const allRoles=element("option","All roles");allRoles.value="";role.append(allRoles);roleLabel.append(role);
            form.append(locationLabel,roleLabel);
        }
        const submit=document.createElement("button");submit.type="submit";submit.textContent="Generate and save report";
        form.append(submit);
        const status=element("p","", "note");status.setAttribute("role","status");status.setAttribute("aria-live","polite");
        const preview=element("section",undefined,"historical-report-preview");
        const history=element("section",undefined,"historical-report-history");
        container.replaceChildren(heading,intro,form,status,preview,history);
        async function loadHistory(){
            const result=await fetchJson(endpoint);
            renderHistory(history,result.reports||[],endpoint);
        }
        form.addEventListener("submit",async event=>{
            event.preventDefault();
            submit.disabled=true;status.textContent="Generating from saved attendance evidence…";
            try{
                const csrfToken=await tokenFor(mode);
                const payload={period:period.value,start:start.value};
                if(mode==="admin"){
                    payload.location=form.elements.location.value.trim();
                    payload.role=form.elements.role.value.trim();
                }
                const result=await fetchJson(endpoint,{
                    method:"POST",
                    headers:{"Content-Type":"application/json","X-CSRF-Token":csrfToken},
                    body:JSON.stringify(payload)
                });
                renderSummary(preview,result.report,result.id,endpoint);
                status.textContent="Historical report saved. Its data is immutable and downloads are rechecked against your current authorization.";
                await loadHistory();
            }catch(error){status.textContent=error.message;}
            finally{submit.disabled=false;}
        });
        submit.disabled=true;
        try{
            await Promise.all([
                loadHistory(),
                mode==="admin"?fetchJson("/api/schedule-locations").then(result=>{
                    if(!Array.isArray(result.scheduleLocations))throw Error("Distribution Centre choices could not be loaded. Reload the page to retry.");
                    for(const entry of result.scheduleLocations){
                        const option=element("option",entry.name);option.value=entry.id;form.elements.location.append(option);
                    }
                    const roles=[...new Set(result.scheduleLocations.map(entry=>entry.roleGroup).filter(value=>typeof value==="string"&&value.trim()))].sort((a,b)=>a.localeCompare(b));
                    for(const value of roles){
                        const option=element("option",value);option.value=value;form.elements.role.append(option);
                    }
                }):Promise.resolve()
            ]);
            submit.disabled=false;
        }catch(error){status.textContent=error.message+" Reload the page to retry; report generation is unavailable until choices and history load.";}
    }
    function scan(){
        const admin=document.getElementById("historicalAttendanceReports");
        if(admin&&!mounted.has(admin))mount(admin,"admin");
        const access=document.getElementById("historicalAccessReports");
        if(access&&!access.hidden&&!mounted.has(access))mount(access,"manager");
    }
    const observer=new MutationObserver(scan);
    function start(){
        if(document.body)observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["hidden"]});
        scan();
    }
    if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start,{once:true});
    else start();
})();
