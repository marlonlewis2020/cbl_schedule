const SCHEDULE_TEMPLATE_BASE="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";
const SCHEDULE_TEMPLATE_FILES=["xl/workbook.xml", "xl/styles.xml", "xl/theme/theme1.xml", "xl/sharedStrings.xml", "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml", "_rels/.rels", "xl/_rels/workbook.xml.rels", "[Content_Types].xml"];
const BAMBOO_CONNECTOR_FILES={
    "README.txt": "CBL SCHEDULING \u2014 LOCAL BAMBOOHR CONNECTOR\n\nRequires Python 3.9 or newer on the computer running the app. No pip packages.\n\n1. Extract every file from this ZIP into one folder.\n2. Windows: double-click Start-Windows.cmd.\n   macOS/Linux: open a terminal in this folder and run: sh start.sh\n3. The connector opens the Scheduling app in your normal browser. Keep the\n   connector window open. If the browser does not open, use the full session\n   URL printed in that window, including the #connector= part.\n4. In Profile, enter your first name and BambooHR API key/API password.\n   BambooHR normally uses x as the API password.\n5. Click Test connection. If successful, Save & continue, then generate schedules.\n\nOpen the app through the connector's browser URL, rather than double-clicking\nits HTML file. This serves both app and connector from the same browser origin\nand avoids direct browser-to-BambooHR cross-origin restrictions.\n\nThe ZIP includes your current scheduling workspace and configuration. If you\nare moving from an older app file, restore its workspace backup in the updated\napp before downloading this kit. API\ncredentials and connector tokens are excluded from this ZIP and from backups.\nEnter the credentials once in the app served by the connector; browser saving\nfor that address is separate from the downloaded HTML's browser storage.\n\nThe connector binds only to 127.0.0.1, accepts a random per-launch session token,\nchecks Host/Origin and proxies only the CBL BambooHR Who's Out endpoint. It does\nnot store API credentials or employee responses on disk and does not log them.\nRequests go from your browser to the connector on your computer, then over\nHTTPS to cbljm.bamboohr.com. Do not expose this connector to a network or use it\nas a shared production server.\n\nClose the launcher window or press Ctrl+C to stop. Each restart changes the\nconnector token, so use the newly opened browser tab or the new session URL.\n\nTroubleshooting:\n- Connection blocked in the downloaded HTML: use the connector browser URL.\n- Connector session expired: use the full URL printed in the launcher window.\n- BambooHR HTTP 401: verify the API key and API password (normally x).\n- BambooHR HTTP 403: the key may lack access to Who's Out or the feature is disabled.\n- Connector cannot reach BambooHR: check internet/VPN/company proxy/certificates.\n- Port busy: close the existing connector, or run python connector.py --port 8766.\n\nIf the API request still fails, the app clearly reports the error and continues\nscheduling without the fresh BambooHR time-off check, as configured.\n", "Start-Windows.cmd": "@echo off\ncd /d \"%~dp0\"\nwhere py >nul 2>nul\nif errorlevel 1 (\n  python connector.py\n) else (\n  py -3 connector.py\n)\necho.\necho If Python was not found, install Python 3, then run this launcher again.\npause\n", "start.sh": "#!/bin/sh\ncd -- \"$(dirname -- \"$0\")\" || exit 1\nexec python3 connector.py\n", "connector.py": "#!/usr/bin/env python3\n\"\"\"CBL loopback-only BambooHR connector. Python 3.9+, standard library only.\"\"\"\nimport argparse\nimport datetime as dt\nimport hmac\nimport json\nfrom http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\nfrom pathlib import Path\nimport secrets\nimport threading\nfrom urllib import error, parse, request\nimport webbrowser\n\nAPP_FILE = 'CBL-Scheduling-Command-Centre.html'\nBAMBOO_URL = 'https://cbljm.bamboohr.com/api/v1/time_off/whos_out'\n\nclass NoRedirect(request.HTTPRedirectHandler):\n    def redirect_request(self, req, fp, code, msg, headers, newurl):\n        return None\n\nclass ConnectorServer(ThreadingHTTPServer):\n    daemon_threads = True\n    def __init__(self, port, app_path, token=None, upstream=None):\n        self.token = token or secrets.token_urlsafe(32)\n        self.app_path = Path(app_path)\n        self.upstream = upstream or self.fetch_bamboo\n        super().__init__(('127.0.0.1', port), ConnectorHandler)\n    def fetch_bamboo(self, start, end, authorization):\n        url = BAMBOO_URL + '?' + parse.urlencode({'start': start, 'end': end})\n        req = request.Request(url, headers={'Accept': 'application/json', 'Authorization': authorization}, method='GET')\n        opener = request.build_opener(NoRedirect())\n        with opener.open(req, timeout=20) as response:\n            data = json.loads(response.read(10_000_001))\n        if not isinstance(data, list):\n            raise ValueError('BambooHR did not return a list of time-off records.')\n        return data\n\nclass ConnectorHandler(BaseHTTPRequestHandler):\n    server_version = 'CBLConnector/1.0'\n    def log_message(self, fmt, *args):\n        pass  # Never log authorization, personal records or request URLs.\n    def allowed_request(self):\n        port = self.server.server_address[1]\n        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}\n        origin = self.headers.get('Origin')\n        return self.headers.get('Host') in hosts and (not origin or origin in {f'http://{host}' for host in hosts})\n    def send_data(self, status, payload, content_type='application/json; charset=utf-8'):\n        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')\n        self.send_response(status)\n        self.send_header('Content-Type', content_type)\n        self.send_header('Content-Length', str(len(body)))\n        self.send_header('Cache-Control', 'no-store')\n        self.send_header('X-Content-Type-Options', 'nosniff')\n        self.send_header('X-Frame-Options', 'DENY')\n        self.send_header('Referrer-Policy', 'no-referrer')\n        if self.allowed_request() and self.headers.get('Origin'):\n            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])\n            self.send_header('Vary', 'Origin')\n        self.end_headers()\n        try:\n            self.wfile.write(body)\n        except (BrokenPipeError, ConnectionResetError):\n            pass\n    def do_OPTIONS(self):\n        if not self.allowed_request() or parse.urlsplit(self.path).path not in {'/bamboo/time-offs', '/health'}:\n            return self.send_data(403, {'error': 'Connector origin or endpoint is not allowed.'})\n        self.send_response(204)\n        if self.headers.get('Origin'):\n            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])\n        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')\n        self.send_header('Access-Control-Allow-Headers', 'Accept, Authorization, X-CBL-Connector-Token')\n        self.send_header('Access-Control-Max-Age', '300')\n        self.end_headers()\n    def do_GET(self):\n        if not self.allowed_request():\n            return self.send_data(403, {'error': 'Connector origin or host is not allowed.'})\n        parsed = parse.urlsplit(self.path)\n        if parsed.path in {'/', '/' + APP_FILE}:\n            try:\n                return self.send_data(200, self.server.app_path.read_bytes(), 'text/html; charset=utf-8')\n            except OSError:\n                return self.send_data(404, {'error': 'Place the Scheduling HTML in the connector folder.'})\n        if parsed.path not in {'/health', '/bamboo/time-offs'}:\n            return self.send_data(404, {'error': 'Unknown connector endpoint.'})\n        token = self.headers.get('X-CBL-Connector-Token', '')\n        if not token or not hmac.compare_digest(token, self.server.token):\n            return self.send_data(403, {'error': 'Connector session expired. Reopen the URL printed by the connector.'})\n        if parsed.path == '/health':\n            return self.send_data(200, {'service': 'cbl-bamboo-local', 'ready': True})\n        authorization = self.headers.get('Authorization', '')\n        if not authorization.startswith('Basic ') or len(authorization) > 8192:\n            return self.send_data(400, {'error': 'BambooHR Basic authorization is required.'})\n        try:\n            query = parse.parse_qs(parsed.query, keep_blank_values=True)\n            if set(query) != {'start', 'end'} or any(len(v) != 1 for v in query.values()):\n                raise ValueError('Provide one start and one end date.')\n            start, end = query['start'][0], query['end'][0]\n            a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)\n            if a.isoformat() != start or b.isoformat() != end or b < a or (b - a).days > 3660:\n                raise ValueError('Invalid date range.')\n        except (ValueError, KeyError):\n            return self.send_data(400, {'error': 'Use valid start/end dates in YYYY-MM-DD format.'})\n        try:\n            data = self.server.upstream(start, end, authorization)\n            return self.send_data(200, data)\n        except error.HTTPError as exc:\n            status = exc.code if exc.code in {400, 401, 403, 404, 422, 429, 500, 502, 503} else 502\n            return self.send_data(status, {'error': f'BambooHR returned HTTP {exc.code}.', 'upstreamStatus': exc.code})\n        except (error.URLError, TimeoutError, OSError):\n            return self.send_data(502, {'error': 'The local connector could not reach BambooHR. Check this computer\u2019s internet, VPN, proxy or certificate configuration.'})\n        except (ValueError, json.JSONDecodeError):\n            return self.send_data(502, {'error': 'BambooHR returned an invalid JSON time-off response.'})\n\n\ndef main():\n    parser = argparse.ArgumentParser(description='Run the local CBL Scheduling app and BambooHR connector.')\n    parser.add_argument('--port', type=int, default=8765)\n    parser.add_argument('--no-browser', action='store_true')\n    args = parser.parse_args()\n    app = Path(__file__).resolve().parent / APP_FILE\n    if not app.is_file():\n        raise SystemExit(f'Keep {APP_FILE} in the same folder as connector.py.')\n    try:\n        server = ConnectorServer(args.port, app)\n    except OSError as exc:\n        raise SystemExit('Cannot start the local connector. Close an existing connector, or run python connector.py --port 8766.') from exc\n    url = f'http://127.0.0.1:{server.server_address[1]}/#connector={server.token}'\n    print('CBL Scheduling local connector is running on this computer only.')\n    print('Leave this window open while using BambooHR. Press Ctrl+C to stop.')\n    print('Open this session in your browser:\\n' + url)\n    if not args.no_browser:\n        threading.Timer(0.5, lambda: webbrowser.open(url)).start()\n    try:\n        server.serve_forever()\n    except KeyboardInterrupt:\n        pass\n    finally:\n        server.server_close()\n\nif __name__ == '__main__':\n    main()\n"
}
;
function scheduleWeeks(m){
    return m.controls.weeks===undefined?Math.max(1,...m.pools.filter(p=>p.enabled).map(p=>Number.isInteger(p.weeks)&&p.weeks>=1&&p.weeks<=52?p.weeks:1)):m.controls.weeks
}
function migrateScheduleWeeks(m){
    m.controls.weeks=scheduleWeeks(m);
    for(let p of m.pools){
        delete p.weeks;
        let previousStarts=Array.isArray(p.shiftStarts)?p.shiftStarts:[...STARTS],previousShares=Array.isArray(p.shares)?p.shares:[];
        if(!Array.isArray(p.shiftStarts))p.shiftStarts=[...STARTS];
        p.shiftStarts=[...new Set(p.shiftStarts.map(Number).filter(s=>Number.isFinite(s)&&s>=0&&s<24))].sort((a,b)=>a-b);
        p.shares=p.shiftStarts.map(s=>{
            let oldIndex=previousStarts.indexOf(s),legacyIndex=STARTS.indexOf(s);
            return oldIndex>=0?previousShares[oldIndex]??0:legacyIndex>=0?previousShares[legacyIndex]??0:0
        });
    }
    for(let e of m.roster){
        if(!e.shiftAvailability||typeof e.shiftAvailability!=='object')e.shiftAvailability={};
        let p=m.pools.find(x=>x.id===key(e.location,e.role));
        for(let s of p?.shiftStarts||STARTS){
            let k=String(s),oldIndex=STARTS.indexOf(s);
            if(e.shiftAvailability[k]===undefined)e.shiftAvailability[k]=oldIndex>=0?e.allow?.[oldIndex]??null:0
        }
    }
    for(let r of m.results||[]){
        let p=m.pools.find(x=>x.id===key(r.location,r.role));
        if(!Array.isArray(r.shiftStarts))r.shiftStarts=[...(p?.shiftStarts||STARTS)];
        for(let e of [...(r.roster||[]),...(r.employees||[])]){
            if(!e.shiftAvailability||typeof e.shiftAvailability!=='object')e.shiftAvailability={};
            for(let s of r.shiftStarts){
                let k=String(s),oldIndex=STARTS.indexOf(s);
                if(e.shiftAvailability[k]===undefined)e.shiftAvailability[k]=oldIndex>=0?e.allow?.[oldIndex]??null:0
            }
        }
    }
    return m
}
'use strict';
const STARTS=[6,8.5,14,22],DAYS=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const isNum=v=>v!==null&&v!==''&&v!==undefined&&Number.isFinite(Number(v)),n=v=>isNum(v)?Number(v):null,clone=o=>JSON.parse(JSON.stringify(o)),key=(l,r)=>l+'|'+r;
function poolStarts(pool){
    return Array.isArray(pool?.shiftStarts)?pool.shiftStarts:STARTS
}
function employeeCanStart(employee,start){
    return employeeStartPermission(employee,start)===1
}
function employeeStartPermission(employee,start){
    let value=employee.shiftAvailability?.[String(start)];
    if(value!==undefined)return value;
    let legacyIndex=STARTS.indexOf(start);
    return legacyIndex>=0?employee.allow?.[legacyIndex]??null:undefined
}
function parseStartTime(value){
    let match=String(value||'').match(/^([01]\d|2[0-3]):([0-5]\d)$/);
    if(!match||Number(match[2])%15!==0)return null;
    return Number(match[1])+Number(match[2])/60
}
function startTimeValue(start){
    let minutes=Math.round(start*60);
    return String(Math.floor(minutes/60)).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0')
}
function isoDate(x){
    if(typeof x==='number')return new Date(Date.UTC(1899,11,30)+x*864e5).toISOString().slice(0,10);
    return typeof x==='string'&&/^\d{4}-\d{2}-\d{2}/.test(x)?x.slice(0,10):''
}
function addDays(date,d){
    return new Date(Date.parse(date+'T00:00:00Z')+d*864e5).toISOString().slice(0,10)
}
function timeLabel(x){
    let h=((x%24)+24)%24,hh=Math.floor(h),m=Math.round((h-hh)*60);
    return (hh%12||12)+':'+String(m).padStart(2,'0')+(hh>=12?' PM':' AM')
}
function shiftLabel(s,span){
    return timeLabel(s)+' – '+timeLabel(s+span)+(s+span>=24?' (+1d)':'')
}
function fromWorkbook(db,name){
    for(let s of ['Roster','Location Roles','Controls','META'])if(!db[s])throw Error('Missing required sheet: '+s);
    if(db.Roster[5]?.[0]!=='ID'||db['Location Roles'][5]?.[0]!=='Location')throw Error('Workbook layout is not compatible. Expected headers on row 6 in Roster and Location Roles.');
    if(db.Roster.slice(206).some(r=>r[0]!==null&&r[0]!==''&&r[0]!==undefined))throw Error('Roster exceeds the source model limit of 200 employees (rows 7–206).');
    let roster=db.Roster.slice(6,206).filter(r=>r[0]!==null&&r[0]!==''&&r[0]!==undefined).map((r,i)=>({
        id:String(r[0]),name:r[1]||'',flex:r[2]??'',reason:r[3]??'',preferred:n(r[4]),proximity:n(r[5]),random:n(r[6]),attendance:n(r[7]),allow:r.slice(8,12).map(n),shiftAvailability:Object.fromEntries(STARTS.map((start,index)=>[String(start),n(r[8+index])])),days:r.slice(12,19).map(n),previous:n(r[19])??-1,location:r[22]||'',role:r[23]||'',index:i
    }
    )),locations=db.META.slice(1).filter(r=>typeof r[0]==='string'&&r[0]).map(r=>({
        name:r[0],intensity:Array.from({
            length:7
        }
        ,(_,i)=>n(r[i+1])),open:Array.from({
            length:7
        }
        ,(_,i)=>n(r[i+9]))
    }
    )),pools=db['Location Roles'].slice(6,46).filter(r=>typeof r[0]==='string'&&typeof r[1]==='string').map((r,i)=>({
        id:key(r[0],r[1]),location:r[0],role:r[1],shiftStarts:[...STARTS],shares:Array.from({
            length:4
        }
        ,(_,j)=>n(r[j+3])),enabled:false,row:i+7
    }
    )),b=i=>db.Controls[i-1]?.[1];
    let c={
        weeks:1,week:isoDate(b(5)),shifts:n(b(7))??5,hours:n(b(8))??8,rest:n(b(9))??11,preference:n(b(10))??2,proximity:n(b(11))??3,random:n(b(12))??1,attendanceEnabled:n(b(13))??1,bonus:n(b(14))??100000,span:9,makeup:1,seed:1,shuffle:true,location:String(b(4)||pools[0]?.location||''),role:String(b(15)||pools[0]?.role||'')
    }
    ;
    let model={
        sourceName:name,sourceImported:new Date().toISOString(),db,roster,locations,pools,controls:c,locked:false,revision:1,lockedAt:null,results:[],selectedRun:'',theme:'light'
    }
    ;
    for(let p of pools){
        let rs=roster.filter(e=>key(e.location,e.role)===p.id);
        p.enabled=rs.length>0&&p.shares.every(isNum)&&Math.abs(p.shares.reduce((a,x)=>a+x,0)-1)<.0001&&rs.every(e=>!rosterErrors(e,p).length)
    }
    return model
}
function rosterErrors(e,pool=model.pools.find(p=>p.id===key(e.location,e.role))){
    let errs=[];
    if(!e.id||!e.name||!e.location||!e.role)errs.push('Identity / pool missing');
    if(!['Yes','No'].includes(e.flex))errs.push('Flexible must be Yes or No');
    if(e.flex==='No'&&!String(e.reason).trim())errs.push('Reason required when not flexible');
    if(!Number.isFinite(e.preferred)||e.preferred<0||e.preferred>=24)errs.push('Preferred start missing / invalid');
    if(![1,2,3].includes(e.proximity))errs.push('Proximity must be 1–3');
    if(![1,2,3].includes(e.random))errs.push('Random factor must be 1–3');
    if(e.attendance!==null&&(!isNum(e.attendance)||e.attendance<0||e.attendance>100))errs.push('Attendance must be 0–100 or blank');
    for(let start of poolStarts(pool))if(![0,1].includes(employeeStartPermission(e,start)))errs.push('Availability for '+timeLabel(start)+' must be 0 or 1');
    if(e.days.length!==7||e.days.some(v=>v!==0&&v!==1))errs.push('Availability must be 0 or 1');
    if(e.flex==='No'&&!employeeCanStart(e,e.preferred))errs.push('Fixed preference is disallowed');
    return errs
}
function poolRoster(m,p){
    return m.roster.filter(e=>e.active!==false&&key(e.location,e.role)===p.id)
}
function modelIssues(m){
    let errors=[],warnings=[],c=m.controls;
    if(!Number.isInteger(scheduleWeeks(m))||scheduleWeeks(m)<1||scheduleWeeks(m)>52)errors.push('Controls: weeks must be a whole number from 1 to 52');
    if(!/^\d{4}-\d{2}-\d{2}$/.test(c.week)||isNaN(Date.parse(c.week)))errors.push('Select a valid week commencing date');
    else if(new Date(c.week+'T00:00:00Z').getUTCDay()!==1)errors.push('Week commencing must be a Monday');
    for(let [k,min,max,int] of [['shifts',1,7,true],['hours',.5,24,false],['span',.5,24,false],['rest',0,48,false],['preference',0,1e6,false],['proximity',0,1e6,false],['random',0,1e6,false],['bonus',0,1e7,false],['seed',0,999999,true]])if(!isNum(c[k])||c[k]<min||c[k]>max||int&&!Number.isInteger(c[k]))errors.push('Controls: invalid '+k);
    if(c.span<c.hours)errors.push('Elapsed shift span must not be less than paid hours');
    if(![0,1].includes(c.attendanceEnabled)||![0,1].includes(c.makeup))errors.push('Priority and make-up switches must be 0 or 1');
    let defined=new Set(m.pools.map(p=>p.id));
    for(let e of m.roster)if(!defined.has(key(e.location,e.role)))warnings.push(e.location+' | '+e.role+': roster employee '+e.name+' has no Location Roles row and will not be scheduled');
    let enabled=m.pools.filter(p=>p.enabled);
    if(!enabled.length)errors.push('Enable at least one location-role pool');
    let seen=new Set();
    for(let e of m.roster){
        if(seen.has(e.id))errors.push('Duplicate employee ID: '+e.id);
        seen.add(e.id)
    }
    for(let p of enabled){
        let rs=poolRoster(m,p),l=m.locations.find(x=>x.name===p.location),prefix=p.id+': ';
        if(rs.length===0||rs.length>21)errors.push(prefix+'roster headcount must be 1–21');
        let starts=poolStarts(p);
        if(!starts.length||new Set(starts).size!==starts.length||starts.some(s=>!Number.isFinite(s)||s<0||s>=24))errors.push(prefix+'shift start times must be unique valid times');
        if(p.shares.length!==starts.length||p.shares.some(x=>!isNum(x)||x<0||x>1)||Math.abs(p.shares.reduce((a,v)=>a+(v||0),0)-1)>.0001)errors.push(prefix+'shift shares must total 100%');
        if(!l)errors.push(prefix+'location missing from META');
        else {
            if(l.open.length!==7||l.open.some(x=>x!==0&&x!==1))errors.push(prefix+'META open flags must be 0/1');
            if(l.intensity.some(x=>!isNum(x)||x<0||x>1))errors.push(prefix+'all seven META intensity values are required (0–100%)');
            let total=l.intensity.reduce((a,x,i)=>a+(l.open[i]===1?(x||0):0),0);
            if(total<=0)errors.push(prefix+'positive intensity on an open day required');
            if(Math.abs(l.intensity.reduce((a,x)=>a+(x||0),0)-1)>.0001)warnings.push(prefix+'daily intensities are normalized over open days');
            if(l.open.filter(x=>x===1).length<c.shifts)warnings.push(prefix+'fewer operating days than weekly shift target');
            if(l.intensity.some((x,i)=>x>0&&!l.open[i]))warnings.push(prefix+'closed-day intensity is excluded from demand');

        }
        for(let e of rs){
            let es=rosterErrors(e,p);
            if(es.length)errors.push(prefix+e.name+' — '+es.join('; '));
            if(!rs.some(x=>x.attendance!==null)&&c.attendanceEnabled)warnings.push(prefix+'attendance priority has no scored employees')
        }

    }

    if(membershipFeatureEnabled('overtimeForecasting')&&typeof overtimeIssues==='function')errors.push(...overtimeIssues(m));
    return {
        errors:[...new Set(errors)],warnings:[...new Set(warnings)]
    }

}
function splitDemand(headcount,shares,c,loc,starts=STARTS){
    let total=headcount*c.shifts,w=loc.intensity.map((x,i)=>loc.open[i]===1?x:0),den=w.reduce((a,x)=>a+x,0),cum=0,prev=0;
    return w.map((x,i)=>{
        cum+=x;let count=Math.round(total*cum/den)-Math.round(total*prev/den);prev=cum;if(!loc.open[i])count=0;let raw=starts.map((_,j)=>(shares[j]||0)*count),req=raw.map(Math.floor),remaining=count-req.reduce((a,x)=>a+x,0),order=raw.map((x,i)=>({
            i,f:x-Math.floor(x)
        }
        )).sort((a,b)=>b.f-a.f||a.i-b.i);for(let j=0;j<remaining;j++)req[order[j].i]++;return req
    }
    )
}
function randomShuffleSeed(previous){
    let v;
    if(globalThis.crypto?.getRandomValues){
        let b=new Uint32Array(1);
        globalThis.crypto.getRandomValues(b);
        v=b[0]%1000000
    }
    else v=Math.floor(Math.random()*1000000);
    return v===previous?(v+1)%1000000:v
}
function shuffleRank(seed,text){
    let h=(2166136261^(Number(seed)>>>0))>>>0;
    for(let i=0;i<text.length;i++){
        h^=text.charCodeAt(i);
        h=Math.imul(h,16777619)>>>0
    }
    h^=h>>>16;
    h=Math.imul(h,0x7feb352d);
    h^=h>>>15;
    h=Math.imul(h,0x846ca68b);
    return (h^(h>>>16))>>>0
}
function generatePool(m,p,start,history=new Map()){
    let c=clone(m.controls),starts=[...poolStarts(p)],rs=poolRoster(m,p).map(clone),location=m.locations.find(l=>l.name===p.location),req=m.requirementsOverride?clone(m.requirementsOverride):splitDemand(rs.length,p.shares,c,location,starts),weekAbs=Date.parse(start+'T00:00:00Z')/36e5,assignment=rs.map(e=>({
        ...e,slots:Array(7).fill(null),types:Array(7).fill(null),rank:0,timeOff:typeof timeOffDays==='function'?timeOffDays(m,e,start):Array(8).fill(false),rotationRandom:1+shuffleRank(c.seed,p.id+'|'+start+'|rotation|'+e.id)%3
    }
    )),priority=[...assignment].filter(e=>e.attendance!==null).sort((a,b)=>b.attendance-a.attendance||a.index-b.index);
    priority.forEach((e,i)=>e.rank=i+1);
    let uncovered=[],audit=[],staff=Array(7).fill(0);

    const count=e=>e.slots.filter(s=>s!==null).length;

    function eligible(e,d,s){
        if(e.timeOff?.[d]||s+c.span>24&&e.timeOff?.[d+1]||!location.open[d]||e.days[d]!==1||e.slots[d]!==null||count(e)>=c.shifts||!employeeCanStart(e,s)||e.flex==='No'&&s!==e.preferred)return false;
        let st=weekAbs+d*24+s,en=st+c.span;
        for(let j=0;j<7;j++)if(e.slots[j]!==null){
            let a=weekAbs+j*24+e.slots[j],b=a+c.span;
            if(st>=b?st-b<c.rest:a>=en?a-en<c.rest:true)return false
        }
        let previous=history.get(e.id);
        if(previous!==undefined&&st-previous<c.rest)return false;
        if(previous===undefined&&e.previous!==-1&&e.previous!==null&&st-(weekAbs-24+e.previous+c.span)<c.rest)return false;
        return true
    }

    function score(e,s,primary){
        return (primary?(c.shifts-count(e))*10000+(e.flex==='No'?1000:0):0)+(s===e.preferred?c.preference:0)+e.proximity*c.proximity+(c.shuffle?e.rotationRandom:e.random)*c.random+(c.attendanceEnabled===1&&e.rank>0&&e.rank<=3&&s===e.preferred?c.bonus:0)
    }

    for(let d=0;d<7;d++){
        let used=Array(starts.length).fill(0),total=req[d].reduce((a,x)=>a+x,0);
        for(let slot=0;slot<total;slot++){
            let choices=starts.map((s,i)=>({
                s,i,left:req[d][i]-used[i],priority:req[d][i]?(req[d][i]-used[i])/req[d][i]:-1
            }
            )).filter(x=>x.left>0).sort((a,b)=>b.priority-a.priority||b.left-a.left||(c.shuffle?shuffleRank(c.seed,p.id+'|'+start+'|'+d+'|slot'+slot+'|'+a.s)-shuffleRank(c.seed,p.id+'|'+start+'|'+d+'|slot'+slot+'|'+b.s):0)||a.s-b.s);
            let {
                s,i
            }
            =choices[0];
            used[i]++;
            let candidates=assignment.filter(e=>eligible(e,d,s)).sort((a,b)=>score(b,s,true)-score(a,s,true)||(c.shuffle?shuffleRank(c.seed,p.id+'|'+start+'|'+d+'|'+s+'|'+a.id)-shuffleRank(c.seed,p.id+'|'+start+'|'+d+'|'+s+'|'+b.id):0)||a.index-b.index);
            if(!candidates.length){
                uncovered.push({
                    day:d,start:s,reason:'No eligible employee'
                }
                );
                continue
            }
            let e=candidates[0];
            audit.push({
                id:e.id,day:d,start:s,type:'Demand',score:score(e,s,true)
            }
            );
            e.slots[d]=s;
            e.types[d]='Demand';
            staff[d]++
        }

    }

    if(c.makeup===1)for(let e of assignment)while(count(e)<c.shifts){
        let options=[];
        for(let d=0;d<7;d++)for(let s of starts)if(eligible(e,d,s))options.push({
            d,s,score:score(e,s,false),staff:staff[d]
        }
        );
        options.sort((a,b)=>b.score-a.score||a.staff-b.staff||(c.shuffle?shuffleRank(c.seed,p.id+'|'+start+'|'+e.id+'|'+a.d+'|'+a.s)-shuffleRank(c.seed,p.id+'|'+start+'|'+e.id+'|'+b.d+'|'+b.s):0)||a.d-b.d||a.s-b.s);
        if(!options.length)break;
        let o=options[0];
        e.slots[o.d]=o.s;
        e.types[o.d]='Make-up';
        staff[o.d]++;
        audit.push({
            id:e.id,day:o.d,start:o.s,type:'Make-up',score:o.score
        }
        )
    }

    for(let e of assignment){
        let last=-Infinity;
        e.slots.forEach((s,d)=>{
            if(s!==null)last=Math.max(last,weekAbs+d*24+s+c.span)
        }
        );
        if(Number.isFinite(last))history.set(e.id,last)
    }

    let controls={
        location:p.location,role:p.role,week:start,headcount:rs.length,...c
    }
    ;
    controls.location=p.location;
    controls.role=p.role;
    controls.week=start;

    return {
        id:key(p.location,p.role)+'|'+start+'|r'+m.revision,location:p.location,role:p.role,shiftStarts:starts,start,end:addDays(start,6),revision:m.revision,createdAt:new Date().toISOString(),timeOffCheck:typeof timeOffCheckSnapshot==='function'?timeOffCheckSnapshot(m):null,controls,shares:clone(p.shares),overtime:typeof overtimeSnapshot==='function'?overtimeSnapshot(m,p,start):null,locationPattern:clone(location),roster:rs,employees:assignment,requirements:req,uncovered,audit,shortages:assignment.filter(e=>count(e)<c.shifts).map(e=>({
            id:e.id,name:e.name,missing:c.shifts-count(e)
        }
        )),makeup:audit.filter(a=>a.type==='Make-up').length,primary:audit.filter(a=>a.type==='Demand').length
    }

}
function generateAll(m,seed=randomShuffleSeed(m.controls.seed)){
    m={
        ...m,controls:{
            ...m.controls,shuffle:true,seed
        }

    }
    ;
    let issues=modelIssues(m);
    if(!m.locked)throw Error('Lock configuration before creating schedules');
    if(issues.errors.length)throw Error(issues.errors.join('\n'));
    let results=[];
    for(let p of m.pools.filter(p=>p.enabled)){
        let history=new Map();
        for(let w=0;w<scheduleWeeks(m);w++)results.push(generatePool(m,p,addDays(m.controls.week,w*7),history))
    }
    return results
}
function validateRun(run){
    let errors=[],c=run.controls;
    for(let e of run.employees){
        if(e.slots.filter(s=>s!==null).length>c.shifts)errors.push('Weekly cap '+e.id);
        let prev=null;
        for(let d=0;d<7;d++){
            let s=e.slots[d];
            if(s===null)continue;
            if(e.timeOff?.[d]||s+c.span>24&&e.timeOff?.[d+1])errors.push('Time-off '+e.id);
            if(!run.locationPattern.open[d]||!e.days[d])errors.push('Closed/unavailable '+e.id);
            if(!employeeCanStart(e,s))errors.push('Permission '+e.id);
            if(e.flex==='No'&&s!==e.preferred)errors.push('Fixed shift '+e.id);
            let st=d*24+s;
            if(prev!==null&&st-prev<c.rest-1e-8)errors.push('Rest '+e.id);
            prev=st+c.span
        }

    }
    for(let d=0;d<7;d++)for(let j=0;j<(run.shiftStarts||STARTS).length;j++){
        let start=(run.shiftStarts||STARTS)[j],filled=run.employees.filter(e=>e.slots[d]===start&&e.types[d]==='Demand').length,missing=run.uncovered.filter(x=>x.day===d&&x.start===start).length;
        if(filled+missing!==run.requirements[d][j])errors.push('Coverage reconciliation')
    }
    return errors
}
async function inflate(bytes,format){
    return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream(format))).arrayBuffer())
}
async function zipEntries(buffer){
    let u=new Uint8Array(buffer),dv=new DataView(buffer),end=u.length-22;
    while(end>=Math.max(0,u.length-65557)&&dv.getUint32(end,true)!==0x06054b50)end--;
    if(end<0)throw Error('Not a valid XLSX ZIP file.');
    let count=dv.getUint16(end+10,true),off=dv.getUint32(end+16,true),files={

    }
    ;
    if(count===65535)throw Error('ZIP64 workbooks are not supported.');
    for(let i=0;i<count;i++){
        if(dv.getUint32(off,true)!==0x02014b50)throw Error('Invalid ZIP directory.');
        let method=dv.getUint16(off+10,true),size=dv.getUint32(off+20,true),nl=dv.getUint16(off+28,true),xl=dv.getUint16(off+30,true),cl=dv.getUint16(off+32,true),local=dv.getUint32(off+42,true),name=new TextDecoder().decode(u.slice(off+46,off+46+nl));
        if(dv.getUint16(off+8,true)&1)throw Error('Encrypted workbooks are not supported.');
        let start=local+30+dv.getUint16(local+26,true)+dv.getUint16(local+28,true);
        files[name]={
            method,bytes:u.slice(start,start+size)
        }
        ;
        off+=46+nl+xl+cl
    }
    return {
        has:n=>!!files[n],text:async n=>{
            if(!files[n])throw Error('Missing workbook component: '+n);
            let f=files[n];
            if(f.method!==0&&f.method!==8)throw Error('Unsupported ZIP compression.');
            return new TextDecoder().decode(f.method===0?f.bytes:await inflate(f.bytes,'deflate-raw'))
        }

    }

}
async function parseXlsx(buffer){
    let z=await zipEntries(buffer),parse=s=>{
        let x=new DOMParser().parseFromString(s,'application/xml');
        if(x.getElementsByTagName('parsererror').length)throw Error('Invalid workbook XML');
        return x
    }
    ,els=(x,n)=>Array.from(x.getElementsByTagNameNS('*',n)),ss=z.has('xl/sharedStrings.xml')?els(parse(await z.text('xl/sharedStrings.xml')),'si').map(si=>els(si,'t').map(t=>t.textContent).join('')):[],styles=z.has('xl/styles.xml')?parse(await z.text('xl/styles.xml')):null,numF={

    }
    ;
    if(styles)els(styles,'numFmt').forEach(x=>numF[x.getAttribute('numFmtId')]=x.getAttribute('formatCode'));
    let dateStyles=styles?els(styles,'cellXfs').flatMap(x=>els(x,'xf')).map(x=>{
        let id=+x.getAttribute('numFmtId'),f=(numF[id]||'').replace(/"[^"]*"|\[[^\]]*\]/g,'');return id>=14&&id<=22||id>=45&&id<=47||/[ymdhis]/i.test(f)
    }
    ):[],wb=parse(await z.text('xl/workbook.xml')),rel=parse(await z.text('xl/_rels/workbook.xml.rels')),rels={

    }
    ;
    els(rel,'Relationship').forEach(x=>rels[x.getAttribute('Id')]=x.getAttribute('Target'));
    let out={

    }
    ,epoch=els(wb,'workbookPr')[0]?.getAttribute('date1904')==='1'?Date.UTC(1904,0,1):Date.UTC(1899,11,30);
    for(let sheet of els(wb,'sheet')){
        let target=rels[sheet.getAttribute('r:id')],path=target.startsWith('/')?target.slice(1):'xl/'+target;
        let xml=parse(await z.text(path)),a=[];
        for(let row of els(xml,'row')){
            let rn=+row.getAttribute('r')-1;
            if(rn>200000)throw Error('Worksheet exceeds supported 200,000 row limit.');
            let r=[];
            for(let c of els(row,'c')){
                let ref=c.getAttribute('r')||'',letters=(ref.match(/^[A-Z]+/)||['A'])[0],j=[...letters].reduce((s,ch)=>s*26+ch.charCodeAt(0)-64,0)-1,t=c.getAttribute('t'),v=els(c,'v')[0]?.textContent,value=null;
                if(t==='s')value=ss[+v]??null;
                else if(t==='inlineStr')value=els(c,'t').map(t=>t.textContent).join('');
                else if(t==='b')value=v==='1';
                else if(t==='str'||t==='e'||t==='d')value=v??null;
                else if(v!==undefined&&v!==''){
                    value=+v;
                    if(dateStyles[+c.getAttribute('s')]){
                        let d=new Date(epoch+value*86400000);
                        value=value>=0&&value<1?d.toISOString().slice(11,19):d.toISOString()
                    }

                }
                r[j]=value
            }
            a[rn]=r
        }
        for(let i=0;i<a.length;i++)a[i]=a[i]||[];
        out[sheet.getAttribute('name')]=a
    }
    return out
}
function allScheduleRows(runs=model.results){
    let h=['Week commencing','Week ending','Location','Role','Revision','Employee ID','Employee','Date','Day','Start','End','End date','Assignment type','Paid hours','Weekly shift target'];
    let a=[h];
    for(let r of runs)for(let e of r.employees)for(let d=0;d<7;d++){
        let s=e.slots[d],date=addDays(r.start,d);
        a.push([r.start,r.end,r.location,r.role,r.revision,e.id,e.name,date,DAYS[d],s===null?(e.timeOff?.[d]?'time-off':'OFF'):timeLabel(s),s===null?'':timeLabel(s+r.controls.span),s===null?'':addDays(date,Math.floor((s+r.controls.span)/24)),s===null?(e.timeOff?.[d]?'Time-off':'OFF'):e.types[d],s===null?0:r.controls.hours,r.controls.shifts])
    }
    return a
}
function safeCSV(a){
    return '\ufeff'+a.map(r=>r.map(x=>{
        let t=String(x??'');if(typeof x!=='number'&&/^[=+@\-]/.test(t))t="'"+t;return '"'+t.replace(/"/g,'""')+'"'
    }
    ).join(',')).join('\r\n')
}
function downloadCSV(){
    downloadFile('CBL-All-Location-Role-Schedules.csv',new Blob([safeCSV(allScheduleRows())],{
        type:'text/csv;charset=utf-8'
    }
    ))
}
function xml(v){
    return String(v??'').replace(/[<>&"']/g,x=>({
        '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'
    }
    [x])).replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g,'')
}
function columnName(i){
    let s='';
    for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;
    return s
}
function sheetXML(a){
    let cols=Math.max(1,...a.map(r=>r.length));
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'+Array.from({
        length:cols
    }
    ,(_,i)=>`<col min="${i+1}" max="${i+1}" width="${i<4?22:18}" customWidth="1"/>`).join('')+'</cols><sheetData>'+a.map((r,i)=>`<row r="${i+1}">${r.map((v,j)=>{
        let c=columnName(j)+(i+1);return typeof v==='number'&&Number.isFinite(v)?`<c r="${c}" s="${i===0?1:0}"><v>${v}</v></c>`:`<c r="${c}" t="inlineStr" s="${i===0?1:0}"><is><t xml:space="preserve">${xml(v)}</t></is></c>`
    }
    ).join('')}</row>`).join('')+'</sheetData><autoFilter ref="A1:'+columnName(cols-1)+Math.max(1,a.length)+'"/></worksheet>'
}
const CRC_TABLE=Array.from({
    length:256
}
,(_,n)=>{
    let c=n;for(let i=0;i<8;i++)c=c&1?0xedb88320^(c>>>1):c>>>1;return c>>>0
}
);
function crc32(b){
    let c=0xffffffff;
    for(let x of b)c=CRC_TABLE[(c^x)&255]^(c>>>8);
    return (c^0xffffffff)>>>0
}
function zipStore(files,type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'){
    let out=[],central=[],offset=0;
    const enc=new TextEncoder();
    for(let [name,input] of Object.entries(files)){
        let nb=enc.encode(name),data=typeof input==='string'?enc.encode(input):input,crc=crc32(data),head=new Uint8Array(30+nb.length),v=new DataView(head.buffer);
        v.setUint32(0,0x04034b50,true);
        v.setUint16(4,20,true);
        v.setUint16(6,0x800,true);
        v.setUint32(14,crc,true);
        v.setUint32(18,data.length,true);
        v.setUint32(22,data.length,true);
        v.setUint16(26,nb.length,true);
        head.set(nb,30);
        out.push(head,data);
        let ch=new Uint8Array(46+nb.length),cv=new DataView(ch.buffer);
        cv.setUint32(0,0x02014b50,true);
        cv.setUint16(4,20,true);
        cv.setUint16(6,20,true);
        cv.setUint16(8,0x800,true);
        cv.setUint32(16,crc,true);
        cv.setUint32(20,data.length,true);
        cv.setUint32(24,data.length,true);
        cv.setUint16(28,nb.length,true);
        cv.setUint32(42,offset,true);
        ch.set(nb,46);
        central.push(ch);
        offset+=head.length+data.length
    }
    let size=central.reduce((s,x)=>s+x.length,0),end=new Uint8Array(22),ev=new DataView(end.buffer);
    ev.setUint32(0,0x06054b50,true);
    ev.setUint16(8,central.length,true);
    ev.setUint16(10,central.length,true);
    ev.setUint32(12,size,true);
    ev.setUint32(16,offset,true);
    return new Blob([...out,...central,end],{type})
}
function workbookBlob(sheets){
    let names=Object.keys(sheets),files={

    }
    ;
    files['[Content_Types].xml']='<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+names.map((n,i)=>`<Override PartName="/xl/worksheets/sheet${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')+'</Types>';
    files['_rels/.rels']='<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
    files['xl/workbook.xml']='<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+names.map((n,i)=>`<sheet name="${xml(n.slice(0,31))}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join('')+'</sheets></workbook>';
    files['xl/_rels/workbook.xml.rels']='<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+names.map((n,i)=>`<Relationship Id="rId${i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i+1}.xml"/>`).join('')+`<Relationship Id="rId${names.length+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`;
    files['xl/styles.xml']='<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF153746"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
    names.forEach((n,i)=>files[`xl/worksheets/sheet${i+1}.xml`]=sheetXML(sheets[n]));
    return zipStore(files)
}
function exportTables(runs=model.results){
    let sheets={
        'All Schedules':allScheduleRows(runs),Coverage:[['Week commencing','Week ending','Location','Role','Revision','Date','Shift','Required','Demand filled','Unfilled','Make-up']],Controls:[['Week commencing','Week ending','Location','Role','Revision','Headcount','Shifts target','Paid hours','Elapsed span','Rest hours','Preference weight','Proximity weight','Random weight','Attendance enabled','Attendance bonus','Make-up enabled','6 AM share','8:30 AM share','2 PM share','10 PM share','Randomized','Shuffle seed']],Shortfalls:[['Week commencing','Location','Role','Employee ID','Employee','Missing shifts']],Notes:[['Topic','Details'],['Source',model.sourceName],['Engine','Browser implementation of scheduling model; generated values, not Excel recalculation.'],['Make-up','Supplemental shifts are additional to primary demand.'],['Dates','Week periods and employee shift dates included.'],['Rest','Rest uses elapsed shift span, including generated consecutive weeks.'],['Revision','Every run has its own saved controls, roster and operating pattern.']]
    }
    ;
    for(let r of runs){
        let c=r.controls;
        sheets.Controls.push([r.start,r.end,r.location,r.role,r.revision,r.employees.length,c.shifts,c.hours,c.span,c.rest,c.preference,c.proximity,c.random,c.attendanceEnabled,c.bonus,c.makeup,...r.shares,c.shuffle?'Yes':'No',c.seed]);
        for(let d=0;d<7;d++)for(let j=0;j<4;j++){
            let got=r.employees.filter(e=>e.slots[d]===STARTS[j]&&e.types[d]==='Demand').length;
            sheets.Coverage.push([r.start,r.end,r.location,r.role,r.revision,addDays(r.start,d),timeLabel(STARTS[j]),r.requirements[d][j],got,r.requirements[d][j]-got,r.employees.filter(e=>e.slots[d]===STARTS[j]&&e.types[d]==='Make-up').length])
        }
        for(let e of r.shortages)sheets.Shortfalls.push([r.start,r.location,r.role,e.id,e.name,e.missing])
    }
    let weekly=[['Week commencing','Week ending','Location','Role','Revision','ID','Employee',...DAYS,'Shifts','Paid hours','Missing shifts']];
    for(let r of runs)for(let e of r.employees)weekly.push([r.start,r.end,r.location,r.role,r.revision,e.id,e.name,...e.slots.map((s,i)=>s===null?(e.timeOff?.[i]?'time-off':'OFF'):shiftLabel(s,r.controls.span)+(e.types[i]==='Make-up'?' +':'')),e.slots.filter(s=>s!==null).length,e.slots.filter(s=>s!==null).length*r.controls.hours,Math.max(0,r.controls.shifts-e.slots.filter(s=>s!==null).length)]);
    return {
        'Weekly Schedules':weekly,...sheets,...(membershipFeatureEnabled('overtimeForecasting')&&typeof overtimeRows==='function'?{
            'Overtime Estimates':overtimeRows(runs)
        }
        :{

        }
        ),...(membershipFeatureEnabled('shiftTrades')&&typeof tradeLogRows==='function'?{
            'Shift Trades':tradeLogRows(runs)
        }
        :{

        }
        ),...(typeof timeOffExportRows==='function'?{
            'Time-offs':timeOffExportRows(runs)
        }
        :{

        }
        )
    }

}
const exportTablesBeforeCustomStarts=exportTables;
exportTables=function(runs=model.results){
    let tables=exportTablesBeforeCustomStarts(runs),starts=[...new Set(runs.flatMap(run=>run.shiftStarts||STARTS))].sort((a,b)=>a-b),controlsHeader=tables.Controls[0].slice(0,16),controlTail=['Randomized','Shuffle seed'];
    tables.Controls=[ [...controlsHeader,...starts.map(start=>timeLabel(start)+' share'),...controlTail] ];
    tables.Coverage=[['Week commencing','Week ending','Location','Role','Revision','Date','Shift','Required','Demand filled','Unfilled','Make-up']];
    for(let run of runs){
        let runStarts=run.shiftStarts||STARTS,shares=new Map(runStarts.map((start,index)=>[start,run.shares[index]]));
        tables.Controls.push([run.start,run.end,run.location,run.role,run.revision,run.employees.length,run.controls.shifts,run.controls.hours,run.controls.span,run.controls.rest,run.controls.preference,run.controls.proximity,run.controls.random,run.controls.attendanceEnabled,run.controls.bonus,run.controls.makeup,...starts.map(start=>shares.get(start)??''),run.controls.shuffle?'Yes':'No',run.controls.seed]);
        for(let day=0;day<7;day++)for(let index=0;index<runStarts.length;index++){
            let start=runStarts[index],required=run.requirements[day][index],demand=run.employees.filter(employee=>employee.slots[day]===start&&employee.types[day]==='Demand').length,makeup=run.employees.filter(employee=>employee.slots[day]===start&&employee.types[day]==='Make-up').length;
            tables.Coverage.push([run.start,run.end,run.location,run.role,run.revision,addDays(run.start,day),timeLabel(start),required,demand,required-demand,makeup])
        }
    }
    return tables
}
function downloadSchedules(){
    if(!model.results.length)throw Error('Generate schedules first');
    downloadFile('CBL-All-Location-Role-Schedules.xlsx',workbookBlob(exportTables()))
}
function inputTables(){
    let roster=[['ID','Employee',...ROSTER_FIELDS.slice(0,6).map(x=>x[1]),...STARTS.map(start=>'Allow '+timeLabel(start)),...ROSTER_FIELDS.slice(6).map(x=>x[1]),'Previous start','Attendance rank','Input check','Location','Role']],meta=[['Location',...DAYS.map(d=>d+' I'),'Total I',...DAYS,'Shift Total']],pools=[['Location','Role','Headcount','6 AM share','8:30 AM share','2 PM share','10 PM share','Enabled']],controls=[['Setting','Value'],...Object.entries(model.controls)],names=model.roster.map(e=>[e.id,e.name,e.flex,e.reason,e.preferred,e.proximity,e.random,e.attendance,...STARTS.map(start=>employeeStartPermission(e,start)??null),...e.days,e.previous,'',rosterErrors(e).length?'CHECK':'OK',e.location,e.role]);
    let availability=[['ID','Employee','Location','Role','Shift start','Allowed']];
    let configuredStarts=[['Location','Role','Shift start','Share']];
    for(let pool of model.pools){
        poolStarts(pool).forEach((start,index)=>configuredStarts.push([pool.location,pool.role,start,pool.shares[index]]));
        for(let employee of model.roster.filter(e=>key(e.location,e.role)===pool.id))for(let start of poolStarts(pool))availability.push([employee.id,employee.name,employee.location,employee.role,start,employeeStartPermission(employee,start)??null]);
    }
    roster.push(...names);
    for(let l of model.locations)meta.push([l.name,...l.intensity,sum(l.intensity.map(x=>x||0)),...l.open,sum(l.open)]);
    for(let p of model.pools)pools.push([p.location,p.role,poolRoster(model,p).length,...STARTS.map(start=>{
        let index=poolStarts(p).indexOf(start);
        return index<0?0:p.shares[index]
    }),p.enabled?1:0]);
    return {
        ...(membershipFeatureEnabled('overtimeForecasting')&&typeof overtimeInputTables==='function'?overtimeInputTables():{

        }
        ),Roster:roster,'Location Roles':pools,'Shift availability':availability,'Configured shift starts':configuredStarts,META:meta,Controls:controls,'Read me':[['Description','Value'],['Export type','Input values snapshot. Original Excel engine formulas are not included.'],['Reimport','Use workspace JSON backup for exact reimport. Upload original-layout source workbooks through Upload source.'],['Source',model.sourceName]]
    }

}
async function downloadInputs(){
    await authorizeDataSettings('configured-inputs');
    downloadFile('CBL-Scheduling-Configured-Inputs.xlsx',workbookBlob(inputTables()))
}
const MENU_GROUPS=[
    {label:'Workspace',pages:[['home','Overview']]},
    {label:'Plan schedules',pages:[['pools','Location roles'],['roster','Roster settings'],['controls','Controls & lock'],['schedules','Weekly schedules']]},
    {label:'People',pages:[['employees','Employees'],['scheduleLocations','Schedule locations'],['attendance','Attendance']]},
    {label:'Integrations',pages:[['publish','Publish to BambooHR'],['links','Workforce Links']]},
    {label:'Data & settings',pages:[['source','Source & backups'],['meta','META · operating days']]}
];
const PAGE_OPTIONS=MENU_GROUPS.flatMap(group=>group.pages);
function appSettings(){
    if(!model.settings||typeof model.settings!=='object')model.settings={

    }
    ;
    let s=model.settings;
    if(!s.menus||typeof s.menus!=='object')s.menus={

    }
    ;
    if(typeof s.workforceCc!=='boolean')s.workforceCc=true;
    if(typeof s.holidays!=='string')s.holidays='';
    return s
}
let businessConfig={
    businessName:'Celebration Brands Limited',teamName:'Schedule Management',logoDataUrl:'',
    primaryColor:'#159bd5',accentColor:'#74bf16',tenantId:'cbljm',apiKeyConfigured:'false'
},bambooPromotionToken='',defaultBusinessLogos=new WeakMap();
async function loadBusinessConfig(){
    businessConfig=await directoryRequest('/app-config');
}
function applyBranding(){
    let business=businessConfig.businessName||'Celebration Brands Limited';
    let team=businessConfig.teamName||'Schedule Management';
    document.title=business+' | Scheduling Command Centre';
    document.querySelector('meta[name="description"]')?.setAttribute('content',business+' scheduling command centre');
    document.querySelectorAll('[data-brand-business]').forEach(element=>element.textContent=business);
    document.querySelectorAll('[data-brand-team]').forEach(element=>element.textContent=team);
    document.querySelectorAll('.brandblock img,.products img').forEach(image=>{
        if(!defaultBusinessLogos.has(image))defaultBusinessLogos.set(image,image.src);
        image.src=businessConfig.logoDataUrl||defaultBusinessLogos.get(image);
        image.alt=businessConfig.logoDataUrl?business:'CBL'
    });
    document.documentElement.style.setProperty('--blue',businessConfig.primaryColor||'#159bd5');
    document.documentElement.style.setProperty('--green',businessConfig.accentColor||'#74bf16');
}
function businessSettingsPanel(){
    let c=businessConfig;
    return panel('Business branding',`<div class="grid"><label>Business name<input id="businessNameSetting" maxlength="120" value="${esc(c.businessName)}"></label><label>Team name<input id="teamNameSetting" maxlength="120" value="${esc(c.teamName)}"></label><label>BambooHR tenant ID<input id="tenantIdSetting" maxlength="63" pattern="[A-Za-z0-9](?:[A-Za-z0-9]|-)*" value="${esc(c.tenantId)}"><small class="note">Used for all BambooHR operations. Saving a different tenant changes the app’s production API URL.</small></label><label>Primary color<input id="primaryColorSetting" type="color" value="${esc(c.primaryColor)}"></label><label>Accent color<input id="accentColorSetting" type="color" value="${esc(c.accentColor)}"></label></div><div class="actions"><button type="button" data-action="pickBusinessLogo">Choose business logo</button><button type="button" data-action="removeBusinessLogo">Remove uploaded logo</button><button class="primary" type="button" data-action="saveBusinessSettings">Save business settings</button><input id="businessLogoFile" type="file" accept="image/png,image/jpeg,image/webp" hidden></div><p class="note">${c.logoDataUrl?'A custom logo is saved.':'No custom logo uploaded; the default logo is shown.'} PNG, JPEG, or WebP · maximum 2 MB. The default team name is Schedule Management.</p>`)+panel('BambooHR API key',`<p>Operational API key: <b>${c.apiKeyConfigured==='true'?'configured':'not configured'}</b>. A tested key is never saved automatically.</p><label>API key for testing<input id="bambooTestApiKey" type="password" maxlength="4096" autocomplete="new-password" placeholder="Enter a key to test"></label><div class="actions"><button type="button" data-action="testBambooKey">Test key for saved tenant</button><button type="button" class="primary" id="promoteBambooKey" data-action="promoteBambooKey" hidden>Use as app API key</button></div><p id="businessKeyStatus" role="status" aria-live="polite"></p><p class="note">Testing performs read-only requests to the tenant’s time-off and time-tracking endpoints. Only after both requests succeed can you explicitly promote the key; it is then stored encrypted for this business only and never shown again.</p>`)+panel('Business membership & administrators',`<p>Manage your business membership and administrators.</p><a class="button" href="/business">Manage membership &amp; administrators</a>`)
}
function pageAllowed(p){
    if(['source','meta'].includes(p)&&!tenantAuthPrimaryAdmin)return false;
    return p==='settings'||['controls','schedules'].includes(p)||PAGE_OPTIONS.some(([id])=>id===p&&appSettings().menus[id]!==false)
}
function settingsPage(){
    let s=appSettings();
    return heading('WORKSPACE / SETTINGS','Choose what your team sees.','Controls & lock and Weekly schedules always remain available. Settings stays accessible so you can re-enable other pages.')+businessSettingsPanel()+accessAccountsPanel()+panel('Upload source',`<p>Current source: <b>${esc(model.sourceName)}</b></p><div class="actions"><button type="button" class="import" data-action="sourcePicker">Upload source</button></div><p class="note">Upload a pre-filled version of the scheduling workbook to replace the configuration basis. Import replaces the editable source configuration and unlocks settings.</p>`)+panel('Sidebar menu',`${MENU_GROUPS.map(group=>`<h3>${esc(group.label)}</h3><div class="settingschecks">${group.pages.map(([id,label])=>`<label class="setting-row"><input type="checkbox" data-menu-setting="${id}" ${pageAllowed(id)?'checked':''} ${['controls','schedules'].includes(id)?'disabled':''}><span><b>${label}</b><small>${['controls','schedules'].includes(id)?'Always available':'Show in sidebar'}</small></span></label>`).join('')}</div>`).join('')}<p class="note">Disabled pages cannot be opened through in-app shortcuts. These workspace preferences are not a security boundary or a replacement for user access permissions.</p>`)+panel('Schedule email',`<label class="setting-row"><input type="checkbox" id="workforceCcSetting" ${s.workforceCc?'checked':''}><span><b>Always Cc workforce@cbljm.co</b><small>Include Workforce in schedule review emails</small></span></label><p class="note">The Cc is fixed in the app’s email composer. Change this option here to omit it. External mail clients allow recipients to edit their drafts.</p><label>Additional non-working dates · one YYYY-MM-DD per line<textarea id="holidaySetting" rows="5" placeholder="2026-12-25">${esc(s.holidays)}</textarea></label><p class="note">Review deadlines exclude the sending date, Saturdays, Sundays and the dates listed above. Public holidays are excluded only when entered here. Dates use Jamaica time. If you send on a later day, regenerate the email to refresh the deadline.</p>`)+panel('Workspace file',`<p>Save this configuration and all saved schedules as a ZIP bundle. Extract all files before opening the included HTML.</p><p class="note">Bundle downloads require the app to be hosted because browsers block access to local CSS and JavaScript files.</p><button type="button" class="primary" data-action="portable">Download Portable ZIP Bundle</button><p class="note">BambooHR API credentials are excluded. Treat the exported bundle as confidential workforce data.</p>`)+overtimeSettingsPanel()
}
function attendanceSortHeader(table,key,label){
    let sort=attendanceSort[table],active=sort.key===key,mark=active?(sort.direction==='asc'?' ▲':' ▼'):'';
    return `<th aria-sort="${active?(sort.direction==='asc'?'ascending':'descending'):'none'}"><button type="button" class="sortheader" data-action="sortAttendance" data-sort-table="${table}" data-sort-key="${key}">${label}${mark}</button></th>`
}
function sortAttendanceItems(table,items,getters){
    let {key,direction}=attendanceSort[table],get=getters[key];
    if(!get)return items;
    let factor=direction==='asc'?1:-1;
    return items.map((item,index)=>({item,index,value:get(item)})).sort((a,b)=>{
        let aEmpty=a.value===null||a.value===undefined||a.value==='',bEmpty=b.value===null||b.value===undefined||b.value==='';
        if(aEmpty||bEmpty)return aEmpty&&bEmpty?a.index-b.index:aEmpty?1:-1;
        let result=typeof a.value==='number'&&typeof b.value==='number'?a.value-b.value:String(a.value).localeCompare(String(b.value),undefined,{numeric:true,sensitivity:'base'});
        return result*factor||a.index-b.index
    }).map(entry=>entry.item)
}
function attendancePage(){
    let data=attendanceData,settings=data?.settings||{latenessToleranceMinutes:15,scorePeriodDays:30},selectedDate=data?.date||attendanceSelectedDate,currentDate=data?.currentDate||selectedDate,sourceInfo=data?.shiftSource||{selected:'app',unresolvedDiscrepancies:null};
    let allShifts=data?.shifts||[],allScores=(data?.scores||[]).filter(item=>item.active);
    let locations=[...new Set([...allShifts,...allScores].map(item=>item.location).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    let roles=[...new Set([...allShifts,...allScores].map(item=>item.role).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    if(!locations.includes(attendanceLocationFilter))attendanceLocationFilter='All';
    if(!roles.includes(attendanceRoleFilter))attendanceRoleFilter='All';
    let matchesFilter=item=>(attendanceLocationFilter==='All'||item.location===attendanceLocationFilter)&&(attendanceRoleFilter==='All'||item.role===attendanceRoleFilter);
    let shifts=sortAttendanceItems('shifts',allShifts.filter(matchesFilter),{date:i=>i.date,name:i=>i.name,location:i=>i.location,role:i=>i.role,shiftStart:i=>Date.parse(i.shiftStart)||null,clockIn:i=>i.clockIn?Date.parse(i.clockIn)||null:null,status:i=>i.status,reason:i=>i.reason}),scores=sortAttendanceItems('scores',allScores.filter(matchesFilter),{name:i=>i.name,location:i=>i.location,role:i=>i.role,attended:i=>i.scheduled?i.attended/i.scheduled:null,computedScore:i=>i.computedScore,score:i=>i.score});
    let summary={expected:0,clockedIn:0,late:0,absent:0,approvedLeave:0,attendancePercent:null};
    for(let item of shifts){
        if(['approved_leave','sick','vacation'].includes(item.status)){
            summary.approvedLeave++;
            continue
        }
        summary.expected++;
        if(['attended','late'].includes(item.status))summary.clockedIn++;
        if(item.status==='late')summary.late++;
        if(item.status==='absent')summary.absent++
    }
    if(summary.expected)summary.attendancePercent=summary.clockedIn*100/summary.expected;
    let shiftRows=shifts.length?shifts.map(item=>`<tr class="${item.overtimeMinutes?'overtime-row':item.earlyMinutes?'early-row':''}"><td>${esc(item.date)}</td><td>${esc(item.name)}<small>${esc(item.employeeId)}</small></td><td>${esc(item.location)}</td><td>${esc(item.role)}</td><td>${esc(new Date(item.shiftStart).toLocaleTimeString())}</td><td>${item.clockIn?esc(new Date(item.clockIn).toLocaleTimeString())+(item.clockOut?' – '+esc(new Date(item.clockOut).toLocaleTimeString()):''):'—'}${item.overtimeMinutes?'<small class="overtime-flag">+'+item.overtimeMinutes+' min past shift end</small>':''}${item.earlyMinutes?'<small class="early-flag">'+item.earlyMinutes+' min left early</small>':''}</td>
<td>${badge(item.status,item.status==='absent'?'bad':item.status==='late'?'warn':item.status==='attended'?'good':'')}</td><td>${esc(item.reason||'')}</td><td><div class="actions employee-actions attendance-actions">${item.canClockIn?`<button type="button" data-action="openAttendanceClockAction" data-clock-action="clock_in" data-run-id="${esc(item.runId)}" data-employee-id="${esc(item.employeeId)}" data-shift-date="${esc(item.date)}" data-shift-start="${esc(item.shiftStart)}" data-name="${esc(item.name)}">Clock in</button>`:''}${item.canClockOut?`<button type="button" data-action="openAttendanceClockAction" data-clock-action="clock_out" data-run-id="${esc(item.runId)}" data-employee-id="${esc(item.employeeId)}" data-shift-date="${esc(item.date)}" data-shift-start="${esc(item.shiftStart)}" data-shift-end="${esc(item.shiftEndAt||'')}" data-name="${esc(item.name)}">Clock out</button>`:''}${item.canClockOutAtShiftEnd?`<button type="button" data-action="openAttendanceClockAction" data-clock-action="clock_out_shift_end" data-run-id="${esc(item.runId)}" data-employee-id="${esc(item.employeeId)}" data-shift-date="${esc(item.date)}" data-shift-start="${esc(item.shiftStart)}" data-shift-end="${esc(item.shiftEndAt||'')}" data-name="${esc(item.name)}">Clock out at shift end</button>`:''}${item.clockActionUnavailableReason?`<span class="note">${esc(item.clockActionUnavailableReason)}</span>`:''}<button type="button" data-action="editAttendanceShift" data-run-id="${esc(item.runId)}" data-employee-id="${esc(item.employeeId)}" data-shift-date="${esc(item.date)}" data-status="${esc(item.status)}" data-name="${esc(item.name)}">Correct</button></div></td></tr>`).join(''):(allShifts.length?'<tr><td colspan="9">No shifts match these filters.</td></tr>':'<tr><td colspan="9">No attendance records are available for this period.</td></tr>');
    let scoreRows=scores.map(item=>`<tr><td>${esc(item.name)}<small>${esc(item.employeeId)}</small></td><td>${esc(item.location)}</td><td>${esc(item.role)}</td><td>${item.attended} / ${item.scheduled}</td><td>${item.computedScore===null?'No data':f(item.computedScore,2)+'%'}</td><td>${item.manualOverride?badge('Manual override','warn'):badge(item.score===null?'No data':f(item.score,2)+'%')}</td><td><div class="actions employee-actions attendance-actions"><button type="button" data-action="editAttendanceScore" data-employee-id="${esc(item.employeeId)}" data-score="${item.score??''}" data-name="${esc(item.name)}" data-manual="${item.manualOverride?'true':'false'}">Set override</button></div></td></tr>`).join('');
    let discrepancies=(sourceInfo.unresolvedDiscrepancies||[]).filter(matchesFilter);
    let discrepancyRows=discrepancies.map(item=>{
        let formatShift=shift=>esc(new Date(shift.start).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}))+'–'+esc(new Date(shift.end).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}))+' · '+esc(shift.location);
        let appShifts=item.appShifts.map(formatShift).join('<br>')||'No accepted app shift';
        let bambooShifts=item.bamboohrShifts.map(formatShift).join('<br>')||'No BambooHR shift';
        return `<tr><td>${esc(item.date)}</td><td>${esc(item.name)}<small>${esc(item.location)} · ${esc(item.role)}</small></td><td>${appShifts}</td><td>${bambooShifts}</td><td><div class="actions employee-actions attendance-actions">${item.canApplyApp?`<button type="button" data-action="reviewAttendanceDiscrepancy" data-discrepancy-id="${esc(item.id)}" data-direction="app_to_bamboohr" data-name="${esc(item.name)}" data-date="${esc(item.date)}">Use app shift</button>`:'<span class="note">App→BambooHR unavailable</span>'}${item.canApplyBambooHR?`<button type="button" data-action="reviewAttendanceDiscrepancy" data-discrepancy-id="${esc(item.id)}" data-direction="bamboohr_to_app" data-name="${esc(item.name)}" data-date="${esc(item.date)}">Use BambooHR shift</button>`:'<span class="note">BambooHR→app unavailable</span>'}</div></td></tr>`
    }).join('');
    let sourceControl=collapsiblePanel('attendance-source','Attendance shift source',`<div class="formgrid"><label>Use shifts from<select id="attendanceShiftSource"><option value="app" ${sourceInfo.selected==='app'?'selected':''}>Accepted shifts in this app</option><option value="bamboohr" ${sourceInfo.selected==='bamboohr'?'selected':''}>BambooHR shifts</option></select></label><div><button type="button" class="primary" data-action="saveAttendanceSource">Save shift source</button></div></div><p class="note">Current source: ${sourceInfo.selected==='app'?'this app’s accepted schedules':'BambooHR schedules'}. BambooHR clock events remain the source of attendance evidence.</p>`)+(sourceInfo.selected==='bamboohr'?collapsiblePanel('attendance-discrepancies','Unresolved BambooHR shift discrepancies',sourceInfo.bamboohrAvailable===true?(discrepancies.length?`<p>${discrepancies.length} unresolved difference${discrepancies.length===1?'':'s'} match the current filters. Differences are rechecked before each resolution.</p><div class="tablewrap"><table><thead><tr><th>Date</th><th>Employee</th><th>Accepted app shift</th><th>BambooHR shift</th><th>Resolution</th></tr></thead><tbody>${discrepancyRows}</tbody></table></div>`:'<p>No unresolved shift discrepancies match the current filters.</p>'):'<p class="badtext">BambooHR shifts could not be checked. Refresh the attendance page before relying on this comparison.</p>'):'');
    return heading('PEOPLE / ATTENDANCE','Track clock-ins against accepted shifts.','The app syncs BambooHR time-tracking and approved time off while this page is open, then rechecks every five minutes. Automatic absence classification runs four hours after shift start.')+
        collapsiblePanel('attendance-sync','BambooHR attendance sync',`<p>${attendanceSyncStatus?`<span class="badtext">${esc(attendanceSyncStatus)}</span>`:data?.lastSyncedAt?`Last successful sync: ${esc(new Date(data.lastSyncedAt).toLocaleString())}`:'Attendance has not synced yet.'}</p><div class="actions"><button type="button" class="primary" data-action="syncAttendance">Sync selected period</button><span class="note">Historical selections fetch up to 365 inclusive days. Automatic polling pauses while this browser tab is hidden or closed.</span></div>`)+
        sourceControl+'<section id="attendanceReports" class="panel"></section><section id="historicalAttendanceReports" class="panel"></section>'+
        collapsiblePanel('attendance-filters','Attendance filters',`<div class="formgrid"><label>Report period${select([['day','Single day'],['months','Month range']],attendancePeriodMode,'id="attendancePeriodMode"')}</label>${attendancePeriodMode==='day'?`<label>Attendance date<input id="attendanceDateFilter" type="date" value="${esc(selectedDate)}" max="${esc(currentDate)}"></label>`:`<label>From month<input id="attendanceStartMonth" type="month" value="${esc(attendanceStartMonth)}" max="${esc(currentDate.slice(0,7))}"></label><label>Through month<input id="attendanceEndMonth" type="month" value="${esc(attendanceEndMonth)}" max="${esc(currentDate.slice(0,7))}"></label>`}<label>Location${select([['All','All locations'],...locations.map(location=>[location,location])],attendanceLocationFilter,'id="attendanceLocationFilter"')}</label><label>Role${select([['All','All roles'],...roles.map(role=>[role,role])],attendanceRoleFilter,'id="attendanceRoleFilter"')}</label></div><p class="note">Month ranges include all recorded shifts from the first month through the selected last month. If attendance has not been synced for that period, choose Sync selected period to fetch it from BambooHR.</p>`)+
        collapsiblePanel('attendance-rules','Attendance rules',`<div class="formgrid"><label>Lateness tolerance · minutes<input id="attendanceTolerance" type="number" min="0" max="120" step="1" value="${settings.latenessToleranceMinutes}"></label><label>Attendance score period · days<input id="attendancePeriod" type="number" min="30" max="45" step="1" value="${settings.scorePeriodDays}"></label></div><div class="actions"><button type="button" class="primary" data-action="saveAttendanceSettings">Save attendance rules</button></div><p class="note">Clock entries count as attendance evidence even if they are awaiting BambooHR approval. Approved leave is excluded from absence classification and the score denominator.</p>`)+
        stats([['Expected shifts',f(summary.expected),'Accepted shifts in selected period'],['Clocked in',f(summary.clockedIn),'Includes late arrivals'],['Attendance',summary.attendancePercent===null?'—':f(summary.attendancePercent,2)+'%','Clocked in ÷ expected'],['Late / absent',f(summary.late)+' / '+f(summary.absent),'Exceptions in selected period'],['Approved leave',f(summary.approvedLeave),'Excluded from attendance rate']])+
        panel(`Attendance · ${esc(data?.periodStart||selectedDate||'')} to ${esc(data?.periodEnd||selectedDate||'')}`,`<div class="tablewrap"><table><thead><tr>${attendanceSortHeader('shifts','date','Date')}${attendanceSortHeader('shifts','name','Employee')}${attendanceSortHeader('shifts','location','Location')}${attendanceSortHeader('shifts','role','Role')}${attendanceSortHeader('shifts','shiftStart','Shift start')}${attendanceSortHeader('shifts','clockIn','Clock-in')}${attendanceSortHeader('shifts','status','Status')}${attendanceSortHeader('shifts','reason','Reason')}<th>Actions</th></tr></thead><tbody>${shiftRows}</tbody></table></div>`)+
        panel(`Attendance scores · selected period`,scores.length?`<div class="tablewrap"><table><thead><tr>${attendanceSortHeader('scores','name','Employee')}${attendanceSortHeader('scores','location','Location')}${attendanceSortHeader('scores','role','Role')}${attendanceSortHeader('scores','attended','Attended / scheduled')}${attendanceSortHeader('scores','computedScore','Calculated')}${attendanceSortHeader('scores','score','Effective')}<th>Actions</th></tr></thead><tbody>${scoreRows}</tbody></table></div>`:(allScores.length?'<p>No active employees match these filters.</p>':'<p>No active employees are available.</p>'))+
        '<dialog id="attendanceOverrideDialog" class="wide-dialog"></dialog><dialog id="attendanceReconciliationDialog" class="wide-dialog"></dialog><dialog id="attendanceClockActionDialog" class="wide-dialog"></dialog>'
}
function openAttendanceClockActionDialog(button){
    const action=button.dataset.clockAction;
    const labels={clock_in:'Clock in',clock_out:'Clock out',clock_out_shift_end:'Clock out at shift end'};
    if(!labels[action])throw Error('Choose a valid attendance clock action.');
    const dialog=workflowDialog('attendanceClockActionDialog');
    const shiftEnd=button.dataset.shiftEnd?new Date(button.dataset.shiftEnd).toLocaleString():'';
    const detail=action==='clock_out_shift_end'
        ?`This will set the BambooHR clock-out to the scheduled shift end (${esc(shiftEnd)}). This action is only available after that time.`
        :'This writes a clock event to BambooHR for the selected employee.';
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">BAMBOOHR CLOCK EVENT</div><h2>${esc(labels[action])} · ${esc(button.dataset.name)}</h2></div><button type="button" data-dialog-close="attendanceClockActionDialog" aria-label="Close">✕</button></div><p>${esc(button.dataset.shiftDate)} · shift starts ${esc(new Date(button.dataset.shiftStart).toLocaleString())}</p><p>${detail}</p><p class="note">The action is sent to BambooHR and audited. Verify the selected employee and shift before confirming.</p><label>Audit reason · required<textarea id="attendanceClockActionReason" maxlength="500" rows="3"></textarea></label><div class="actions"><button type="button" class="primary" data-action="submitAttendanceClockAction" data-clock-action="${esc(action)}" data-request-id="${esc(crypto.randomUUID())}" data-run-id="${esc(button.dataset.runId)}" data-employee-id="${esc(button.dataset.employeeId)}" data-shift-date="${esc(button.dataset.shiftDate)}">Confirm ${esc(labels[action].toLowerCase())}</button><button type="button" data-dialog-close="attendanceClockActionDialog">Cancel</button></div>`;
    if(!dialog.open)dialog.showModal()
}
function openAttendanceReconciliationDialog(button){
    let direction=button.dataset.direction,copy=direction==='app_to_bamboohr'?'Replace the BambooHR shift with the accepted app shift.':'Update the accepted app schedule to match BambooHR.';
    let dialog=workflowDialog('attendanceReconciliationDialog');
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">AUDITABLE SHIFT RECONCILIATION</div><h2>${esc(button.dataset.name)} · ${esc(button.dataset.date)}</h2></div><button type="button" data-dialog-close="attendanceReconciliationDialog" aria-label="Close">✕</button></div><p>${copy}</p>${direction==='app_to_bamboohr'?'<p class="note">BambooHR replacement is a separate add-then-delete operation. If only one step succeeds, the app will report the partial result; refresh before retrying.</p>':''}<label>Reason · required<textarea id="attendanceReconciliationReason" maxlength="500" rows="3"></textarea></label><div class="actions"><button type="button" class="primary" data-action="resolveAttendanceDiscrepancy" data-discrepancy-id="${esc(button.dataset.discrepancyId)}" data-direction="${esc(direction)}" data-date="${esc(button.dataset.date)}">Confirm and resolve</button><button type="button" data-dialog-close="attendanceReconciliationDialog">Cancel</button></div>`;
    if(!dialog.open)dialog.showModal()
}
function openAttendanceScoreDialog(button){
    let item=(attendanceData?.scores||[]).find(score=>String(score.employeeId)===button.dataset.employeeId);
    if(!item)throw Error('The selected employee attendance score could not be found.');
    let dialog=workflowDialog('attendanceOverrideDialog');
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">AUDITABLE OVERRIDE</div><h2>Attendance score · ${esc(item.name)}</h2></div><button type="button" data-dialog-close="attendanceOverrideDialog" aria-label="Close">✕</button></div><p>Calculated score: ${item.computedScore===null?'No data':f(item.computedScore,2)+'%'} · ${item.attended} attended of ${item.scheduled} scheduled shifts.</p><label>Override score · 0–100<input id="attendanceOverrideScore" type="number" min="0" max="100" step="0.01" value="${item.score??''}"></label><label>Reason · required<textarea id="attendanceOverrideReason" maxlength="500" rows="3"></textarea></label><div class="actions"><button type="button" data-action="saveAttendanceScoreOverride" data-employee-id="${esc(item.employeeId)}">Save override</button>${item.manualOverride?`<button type="button" class="danger" data-action="removeAttendanceScoreOverride" data-employee-id="${esc(item.employeeId)}">Remove override</button>`:''}<button type="button" data-dialog-close="attendanceOverrideDialog">Cancel</button></div>`;
    if(!dialog.open)dialog.showModal()
}
function openAttendanceShiftDialog(button){
    let dialog=workflowDialog('attendanceOverrideDialog');
    let options=[['attended','Attended'],['late','Late'],['absent','Absent'],['sick','Sick'],['vacation','Vacation'],['approved_leave','Approved leave']];
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">AUDITABLE CORRECTION</div><h2>Attendance · ${esc(button.dataset.name)}</h2></div><button type="button" data-dialog-close="attendanceOverrideDialog" aria-label="Close">✕</button></div><p>${esc(button.dataset.shiftDate)} · Current status: ${esc(button.dataset.status)}</p><label>Corrected status ${select(options,button.dataset.status,'id="attendanceShiftStatus"')}</label><label>Reason · required<textarea id="attendanceShiftReason" maxlength="500" rows="3"></textarea></label><div class="actions"><button type="button" class="primary" data-action="saveAttendanceShiftOverride" data-run-id="${esc(button.dataset.runId)}" data-employee-id="${esc(button.dataset.employeeId)}" data-shift-date="${esc(button.dataset.shiftDate)}">Save correction</button><button type="button" data-dialog-close="attendanceOverrideDialog">Cancel</button></div>`;
    if(!dialog.open)dialog.showModal()
}
function setNavGroupOpen(group,open){
    group.classList.toggle('collapsed',!open);
    group.querySelector('.nav-group-title')?.setAttribute('aria-expanded',String(open));
    let title=group.querySelector('.nav-group-title'),caret=title?.querySelector('i');
    if(caret)caret.textContent=open?'▾':'▸'
}
function initNavGroups(){
    document.querySelectorAll('#appMenu .nav-group').forEach(group=>{
        let title=group.querySelector('.nav-group-title');
        if(!title||title.dataset.ready)return;
        title.dataset.ready='1';
        title.setAttribute('role','button');
        title.tabIndex=0;
        title.insertAdjacentHTML('beforeend','<i aria-hidden="true"></i>');
        let toggle=()=>{
            let open=group.classList.contains('collapsed');
            document.querySelectorAll('#appMenu .nav-group').forEach(other=>setNavGroupOpen(other,open&&other===group))
        };
        title.addEventListener('click',toggle);
        title.addEventListener('keydown',e=>{
            if(e.key==='Enter'||e.key===' '){
                e.preventDefault();
                toggle()
            }
        });
        setNavGroupOpen(group,false)
    })
}
function applyMenuSettings(){
    initNavGroups();
    if(!pageAllowed(page))page='controls';
    document.querySelectorAll('[data-page]').forEach(e=>{
        e.hidden=!pageAllowed(e.dataset.page)
    }
    );
    document.querySelectorAll('#appMenu .nav-group').forEach(group=>{
        group.hidden=!group.querySelector('[data-page]:not([hidden])')
    });
    document.querySelectorAll('#content [data-action="sourcePicker"],#content [data-action="portable"]').forEach(button=>{
        button.closest('.panel').hidden=!tenantAuthPrimaryAdmin
    });
    document.querySelectorAll('[data-menu-setting="source"],[data-menu-setting="meta"]').forEach(preference=>{
        preference.disabled=!tenantAuthPrimaryAdmin;
        preference.closest('label').hidden=!tenantAuthPrimaryAdmin;
        preference.closest('.settingschecks').previousElementSibling.hidden=!tenantAuthPrimaryAdmin;
    });
}
function jamaicaDate(now=new Date()){
    let p=new Intl.DateTimeFormat('en-CA',{
        timeZone:'America/Jamaica',year:'numeric',month:'2-digit',day:'2-digit'
    }
    ).formatToParts(now);
    return ['year','month','day'].map(k=>p.find(x=>x.type===k).value).join('-')
}
function businessDeadline(sent,holidays=''){
    let excluded=new Set(holidays.split(/[\s,;]+/).filter(Boolean)),d=sent,n=0;
    while(n<5){
        d=addDays(d,1);
        let day=new Date(d+'T12:00:00Z').getUTCDay();
        if(day!==0&&day!==6&&!excluded.has(d))n++
    }
    return d
}
function prettyDate(d){
    return new Intl.DateTimeFormat('en-JM',{
        timeZone:'UTC',weekday:'long',day:'numeric',month:'long',year:'numeric'
    }
    ).format(new Date(d+'T12:00:00Z'))
}
function titleName(name){
    return name.trim().replace(/\s+/g,' ').toLocaleLowerCase().replace(/(^|[\s\-'’])\p{L}/gu,c=>c.toLocaleUpperCase())
}
function validEmail(v){
    return /^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$/.test(v)&&!/[\r\n]/.test(v)
}
function emailManagerGroups(ids){
    let runs=model.results.filter(run=>ids.includes(run.id)),groups=new Map();
    if(!runs.length)throw Error('Select at least one generated schedule.');
    for(let run of runs){
        let assigned=run.employees.filter(employee=>employee.slots.some(start=>start!==null));
        let locationIds=new Set(assigned.map(employee=>employeeDirectory.find(item=>item.id===String(employee.id))?.scheduleLocationId).filter(Boolean));
        if(assigned.some(employee=>!employeeDirectory.find(item=>item.id===String(employee.id))?.scheduleLocationId)){
            throw Error('Assign every scheduled employee to a schedule location before preparing manager confirmation emails.')
        }
        if(!locationIds.size){
            let matches=scheduleLocations.filter(location=>location.location===run.location&&roleFitsScheduleGroup(run.role,location));
            if(matches.length!==1)throw Error('Could not identify one schedule location for '+run.location+' · '+run.role+'. Assign employees or review the schedule location role groups.');
            locationIds.add(matches[0].id)
        }
        if(locationIds.size!==1)throw Error('The schedule for '+run.location+' · '+run.role+' contains employees from multiple schedule locations. Prepare separate site schedules before emailing managers.');
        let location=scheduleLocations.find(item=>item.id===[...locationIds][0]);
        if(!location)throw Error('The schedule location for '+run.location+' · '+run.role+' is no longer available.');
        if(!location.managerName?.trim()||!validEmail(location.managerEmail||'')){
            throw Error('Add a valid manager name and email for '+location.name+' in Schedule Locations before preparing the confirmation email.')
        }
        if(!groups.has(location.id))groups.set(location.id,{location,manager:{name:location.managerName,email:location.managerEmail},runs:[]});
        groups.get(location.id).runs.push(run)
    }
    return [...groups.values()]
}
function managerEmailPackage(group,sent=jamaicaDate()){
    let people=[{name:group.manager.name.trim(),email:group.manager.email.trim()}];
    let cc=appSettings().workforceCc?'workforce@cbljm.co':'',deadline=businessDeadline(sent,appSettings().holidays),periods=[...new Set(group.runs.map(run=>run.start+' to '+run.end))],subject='Schedule review and confirmation — '+group.location.name+' — '+(periods.length===1?periods[0]:periods.length+' weekly periods'),body='Dear '+people[0].name+',\n\nPlease review the attached workbook containing the following proposed schedules for '+group.location.name+':\n\n'+group.runs.map(run=>'• '+run.location+' — '+run.role+' | '+run.start+' to '+run.end+' | revision '+run.revision).join('\n')+'\n\nPlease confirm the schedules or provide any required changes no later than '+prettyDate(deadline)+' (five business days from '+prettyDate(sent)+'). Please check employee availability, shift coverage and any scheduling conflicts, and reply to all with your confirmation or requested changes.\n\nThank you,\n'+(businessConfig.teamName||'Schedule Management')+'\n'+(businessConfig.businessName||'Celebration Brands Limited');
    let businessFileName=(businessConfig.businessName||'Business').trim().replace(/[^A-Za-z0-9]+/g,'-').replace(/^-|-$/g,'');
    return {people,runs:group.runs,location:group.location,cc,subject,body,sent,deadline,filename:businessFileName+'-Schedules-for-Review-'+group.location.name.replace(/[^A-Za-z0-9]+/g,'-')+'-'+sent+'.xlsx'}
}
function openEmail(){
    if(!model.results.length){
        message('Generate schedules before preparing an email.',true);
        return
    }
    let dlg=$('emailDialog');
    dlg.innerHTML=`<div id="emailForm"><div class="dialoghead"><div><div class="eyebrow">SCHEDULE REVIEW</div><h2>Prepare manager confirmation email</h2></div><button type="button" data-email-command="close" aria-label="Close">✕</button></div><p>Select schedules to include. The app groups them by schedule location and sends each manager only schedules for their site.</p><fieldset><legend>1 · Select generated schedules</legend><div class="actions"><button type="button" data-email-command="selectAll">Select all</button><button type="button" data-email-command="selectNone">Clear</button></div><div class="schedulechoices">${model.results.map(r=>`<label><input type="checkbox" data-email-run value="${esc(r.id)}" ${r.id===model.selectedRun?'checked':''}> <span><b>${esc(r.location)} · ${esc(r.role)}</b><small>${r.start} to ${r.end} · revision ${r.revision}</small></span></label>`).join('')}</div></fieldset><fieldset><legend>2 · Manager email</legend><label>Schedule location ${select([],'','id="emailManagerGroup"')}</label><p id="emailManagerDetails">Preview the selection to identify the schedule-location managers.</p><p>Cc: <strong>${appSettings().workforceCc?'workforce@cbljm.co · fixed in Settings':'Disabled in Settings'}</strong></p></fieldset><div class="callout">The default mail client receives one manager-specific draft at a time. Download that location’s workbook and attach it before sending. The app prepares drafts; it does not send messages automatically.</div><div class="actions"><button type="button" data-email-command="preview" class="primary">Preview manager email & workbook</button></div><p id="emailError" class="badtext" role="alert"></p><section id="emailPreview" hidden><h3>Email preview</h3><p id="emailDeadline"></p><label>Subject<input id="emailSubject" readonly></label><label>Message<textarea id="emailBody" rows="12" readonly></textarea></label><div class="actions"><button type="button" data-email-command="workbook">1 · Download this manager’s schedules · XLSX</button><button type="button" data-email-command="client">2 · Open manager email draft</button><button type="button" data-email-command="copy">Copy full email template</button><button type="button" data-email-command="template">Download email template · TXT</button></div><p class="note">Repeat for each schedule location in the selector. Attach the downloaded XLSX before sending.</p></section></div>`;
    const portalLabel=document.createElement('label'),portalCheck=document.createElement('input');
    portalCheck.type='checkbox';portalCheck.id='emailPortalCodes';
    portalCheck.checked=acceptedSchedules.some(item=>item.id===model.selectedRun);
    portalLabel.append(portalCheck,document.createTextNode(' Include employee portal codes (accept schedules first; current visibility window only).'));
    dlg.querySelector('#emailForm fieldset:last-of-type').append(portalLabel);
    refreshEmailManagerGroups();
    dlg.showModal();

}
let preparedEmail=null;
let preparedManagerGroups=[];
let preparedEmailGeneration=0;
function refreshEmailManagerGroups(){
    preparedEmailGeneration++;
    preparedEmail=null;
    $('emailPreview').hidden=true;
    let selector=$('emailManagerGroup'),selected=selector.value;
    try{
        let ids=[...$('emailDialog').querySelectorAll('[data-email-run]:checked')].map(e=>e.value);
        preparedManagerGroups=emailManagerGroups(ids);
        selector.innerHTML=preparedManagerGroups.map(group=>`<option value="${esc(group.location.id)}">${esc(group.location.name)} · ${esc(group.manager.name)} · ${esc(group.manager.email)} · ${group.runs.length} schedules</option>`).join('');
        selector.disabled=false;
        selector.value=preparedManagerGroups.some(group=>group.location.id===selected)?selected:preparedManagerGroups[0].location.id;
        let group=preparedManagerGroups.find(item=>item.location.id===selector.value);
        $('emailManagerDetails').textContent='To: '+group.manager.name+' <'+group.manager.email+'> · '+group.runs.length+' selected schedule(s) for '+group.location.name+'.';
        $('emailError').textContent='';
        return group
    }
    catch(error){
        preparedManagerGroups=[];
        selector.replaceChildren();
        selector.disabled=true;
        $('emailManagerDetails').textContent='Select valid schedules with configured location managers.';
        $('emailError').textContent=error.message;
        return null
    }
}
async function prepareEmail(){
    let group=refreshEmailManagerGroups();
    if(!group)return null;
    const generation=++preparedEmailGeneration;
    try{
        let draft=managerEmailPackage(group);
        if($('emailPortalCodes').checked){
            let codes=(await directoryRequest('/schedule-portal/codes',{
                method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({runIds:group.runs.map(run=>run.id)})
            })).codes.filter(item=>item.locationId===group.location.id);
            if(new Set(codes.map(item=>item.runId)).size!==group.runs.length)throw Error('The accepted schedules no longer match this manager location. Refresh the schedules and employee assignments.');
            draft.body+='\n\nEmployee schedule portal: '+new URL('/access',window.location.href).href+
                '\nEmployees must sign in individually and have an assignment in the period. Share the appropriate code securely with the team:\n'+
                codes.map(item=>item.role+' | '+item.start+' to '+item.end+' | Code: '+item.code+' | Expires: '+item.expiresAt+' (Jamaica)').join('\n');
        }
        if(generation!==preparedEmailGeneration)return null;
        preparedEmail=draft;
        $('emailSubject').value=preparedEmail.subject;
        $('emailBody').value=preparedEmail.body;
        $('emailDeadline').textContent='Prepared: '+prettyDate(preparedEmail.sent)+' · Confirmation due: '+prettyDate(preparedEmail.deadline);
        $('emailPreview').hidden=false;
        $('emailError').textContent='';
        return preparedEmail
    }
    catch(e){
        if(generation!==preparedEmailGeneration)return null;
        preparedEmail=null;
        $('emailPreview').hidden=true;
        $('emailError').textContent=e.message;
        return null
    }

}
function emailTemplate(p){
    return 'To: '+p.people.map(x=>x.name+' <'+x.email+'>').join('; ')+'\nCc: '+p.cc+'\nSubject: '+p.subject+'\nAttachment: '+p.filename+'\n\n'+p.body
}
function mailtoUrl(p){
    return 'mailto:'+p.people.map(x=>encodeURIComponent(x.email)).join(',')+'?'+new URLSearchParams({
        cc:p.cc,subject:p.subject,body:p.body
    }
    ).toString().replace(/\+/g,'%20')
}
document.addEventListener('change',e=>{
    if(!model)return;let t=e.target;if(t.dataset.menuSetting){
        let id=t.dataset.menuSetting;if(!['controls','schedules'].includes(id))appSettings().menus[id]=t.checked;render();queueSave()
    }
    if(t.id==='attendanceLocationFilter'||t.id==='attendanceRoleFilter'){
        if(t.id==='attendanceLocationFilter')attendanceLocationFilter=t.value;
        else attendanceRoleFilter=t.value;
        render();
        return
    }
    if(['attendancePeriodMode','attendanceDateFilter','attendanceStartMonth','attendanceEndMonth'].includes(t.id)){
        if(t.id==='attendancePeriodMode')attendancePeriodMode=t.value;
        if(t.id==='attendanceDateFilter')attendanceSelectedDate=t.value;
        if(t.id==='attendanceStartMonth')attendanceStartMonth=t.value;
        if(t.id==='attendanceEndMonth')attendanceEndMonth=t.value;
        loadSelectedAttendance().catch(error=>{
            attendanceSyncStatus=error.message;
            if(page==='attendance')render(true)
        });
        return
    }
    if(t.id==='workforceCcSetting'){
        appSettings().workforceCc=t.checked;queueSave()
    }
    if(t.matches('[data-email-run]')||t.id==='emailManagerGroup')refreshEmailManagerGroups();
    if(t.id==='holidaySetting'){
        let dates=t.value.trim().split(/\s+/).filter(Boolean);if(dates.some(d=>!/^\d{4}-\d{2}-\d{2}$/.test(d)||Number.isNaN(Date.parse(d+'T12:00:00Z'))||new Date(d+'T12:00:00Z').toISOString().slice(0,10)!==d)){
            message('Enter valid non-working dates, one YYYY-MM-DD per line.',true);t.value=appSettings().holidays;return
        }
        appSettings().holidays=dates.join('\n');queueSave()
    }

}
);
document.addEventListener('input',e=>{
    if(e.target.closest?.('#emailForm')&&$('emailPreview')){
        preparedEmailGeneration++;
        preparedEmail=null;$('emailPreview').hidden=true
    }

}
);
document.addEventListener('click',async e=>{
    let b=e.target.closest('[data-email-command]');if(!b)return;let cmd=b.dataset.emailCommand;if(cmd==='close'){
        $('emailDialog').close();preparedEmailGeneration++;preparedEmail=null;return
    }
    if(cmd==='selectAll'||cmd==='selectNone'){
        preparedEmailGeneration++;
        $('emailDialog').querySelectorAll('[data-email-run]').forEach(x=>x.checked=cmd==='selectAll');refreshEmailManagerGroups();return
    }
    let p=await prepareEmail();if(!p)return;try{
        if(cmd==='workbook')downloadFile(p.filename,workbookBlob(exportTables(p.runs)));if(cmd==='client'){
            let url=mailtoUrl(p);if(url.length>7000)throw Error('This message is too long for a reliable email link. Use Copy full email template instead.');window.location.href=url;$('emailError').textContent='Mail client requested. Download and attach '+p.filename+' before sending.'
        }
        if(cmd==='template')downloadFile('CBL-Schedule-Email-'+p.sent+'.txt',new Blob([emailTemplate(p)],{
            type:'text/plain;charset=utf-8'
        }
        ));if(cmd==='copy'){
            try{
                await navigator.clipboard.writeText(emailTemplate(p));$('emailError').textContent='Email template copied, including To, Cc and subject.'
            }
            catch{
                downloadFile('CBL-Schedule-Email-'+p.sent+'.txt',new Blob([emailTemplate(p)],{
                    type:'text/plain;charset=utf-8'
                }
                ));$('emailError').textContent='Clipboard unavailable. Email template downloaded as text instead.'
            }

        }

    }
    catch(err){
        $('emailError').textContent=err.message
    }

}
);
const WORKFORCE_LINKS=[["Workforce Command Centre", "https://cbljm.sharepoint.com/:x:/r/sites/TeamHR/_layouts/15/Doc.aspx?sourcedoc=%7B9D205D8A-E2A3-45FF-95B6-5897231A5306%7D&file=Workforce%20Command%20Centre%20%26%20SDG.xlsx&action=default&mobileredirect=true&wdwpf=doclib-t"], ["Workforce Time Tracking", "https://cbljm.sharepoint.com/:x:/r/sites/TeamHR/_layouts/15/Doc.aspx?sourcedoc=%7BE98BAF89-E458-444F-839A-371EAC8C2503%7D&file=Workforce%20-%20Time%20Tracking.xlsx&action=default&mobileredirect=true&wdwpf=doclib-t"], ["Shifts Log", "https://cbljm.sharepoint.com/:x:/r/sites/TeamHR/_layouts/15/Doc.aspx?sourcedoc=%7B6D2C4B79-5C53-45B2-9807-851579FB556D%7D&file=Shifts.xlsx&action=default&mobileredirect=true&wdwpf=doclib-t"], ["Scheduling Matrix", "https://cbljm.sharepoint.com/:x:/r/sites/TeamHR/_layouts/15/Doc.aspx?sourcedoc=%7BBC4F3586-9271-49FB-A802-9CE9247CB8CD%7D&file=Weekly_Scheduling_Matrix_by_Role.xlsx&action=default&mobileredirect=true&wdwpf=doclib-t"], ["BambooHR API Documentation", "https://documentation.bamboohr.com/reference/"], ["BambooHR", "https://cbljm.bamboohr.com/"], ["TeamHR Sharepoint site", "https://cbljm.sharepoint.com/sites/TeamHR/SitePages/CollabHome.aspx"]];
function workforceLinksPage(){
    return heading("WORKFORCE / RESOURCES","Workforce Links","Open the shared workbooks, HR tools and documentation in a new tab.")+panel("Workforce resources",`<div class="workforce-links">${WORKFORCE_LINKS.map(([label,url],i)=>`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer"><span class="resource-number">${String(i+1).padStart(2,"0")}</span><span><b>${esc(label)}</b><small>${url.includes("sharepoint")?"Microsoft SharePoint":url.includes("documentation")?"Developer reference":"Employee platform"} · opens in a new tab</small></span><span aria-hidden="true">↗</span></a>`).join("")}</div>`)
}
function warehouseRole(role){
    return String(role).trim().toLowerCase()==='warehouse'
}
function overtimeConfig(m=model){
    if(!m.overtime||typeof m.overtime!=='object')m.overtime={

    }
    ;
    let o=m.overtime;
    for(let k of ['capacity','minimum','volumes'])if(!o[k]||typeof o[k]!=='object'||Array.isArray(o[k]))o[k]={

    }
    ;
    if(typeof o.unit!=='string'||!o.unit.trim())o.unit='units';
    return o
}
function positiveNumber(v){
    return isNum(v)&&Number(v)>0?Number(v):null
}
function validShares(s){
    return Array.isArray(s)&&s.length>0&&s.every(x=>isNum(x)&&x>=0&&x<=1)&&Math.abs(s.reduce((a,x)=>a+Number(x),0)-1)<.0001
}
function allocateMinimum(total,shares){
    let raw=shares.map(x=>x*total),counts=raw.map(Math.floor),left=total-counts.reduce((a,x)=>a+x,0),order=raw.map((x,i)=>({
        i,f:x-Math.floor(x)
    }
    )).sort((a,b)=>b.f-a.f||a.i-b.i);
    for(let i=0;i<left;i++)counts[order[i].i]++;
    return counts
}
function overtimeSnapshot(m,p,start){
    let o=overtimeConfig(m);
    return {
        version:1,unit:o.unit,capacity:positiveNumber(o.capacity[p.location]),minimum:positiveNumber(o.minimum[p.id]),volumes:Array.from({
            length:7
        }
        ,(_,d)=>{
            let v=o.volumes[p.location]?.[addDays(start,d)];return isNum(v)&&Number(v)>=0?Number(v):null
        }
        )
    }

}
function overtimeEstimate(run){
    let o=run.overtime,warehouse=warehouseRole(run.role),basis=warehouse?'Warehouse volume':'Minimum daily headcount',rows=[];
    for(let d=0;d<7;d++){
        let volume=warehouse?o?.volumes?.[d]??null:null,capacity=warehouse?positiveNumber(o?.capacity):null,minimum=warehouse?null:positiveNumber(o?.minimum),open=run.locationPattern.open[d]===1,status=!o?'No overtime configuration saved':warehouse?!capacity?'No FTE capacity set':volume===null?'No daily volume entered':!open&&volume>0?'Closed day — review operating calendar':'Ready':!minimum?'No minimum headcount set':!open?'Closed day — no minimum demand':'Ready';
        if(!validShares(run.shares))status='Shift shares incomplete';
        let ready=status==='Ready',needed=ready?(warehouse?run.shares.map(s=>volume*s/capacity):allocateMinimum(minimum,run.shares)):null;
        for(let j=0;j<(run.shiftStarts||STARTS).length;j++){
            let start=(run.shiftStarts||STARTS)[j],staff=run.employees.filter(e=>e.slots[d]===start).length,required=needed?.[j]??null,short=required===null?null:Math.max(0,required-staff),hours=short===null?null:Math.ceil(Math.max(0,short*run.controls.hours-1e-9)*100)/100;
            rows.push({
                date:addDays(run.start,d),day:DAYS[d],start,basis,status,open,volume:warehouse&&volume!==null?volume*run.shares[j]:null,capacity,minimum,required,staff,short,hours
            }
            )
        }

    }
    return rows
}
function overtimePanel(run){
    if(!membershipFeatureEnabled('overtimeForecasting'))return panel('Overtime planning','<p>Overtime forecasting is included with Gold and above.</p>');
    let rows=overtimeEstimate(run),known=rows.filter(r=>r.hours!==null),total=known.reduce((n,r)=>n+r.hours,0),days=Array.from({
        length:7
    }
    ,(_,d)=>rows.slice(d*4,d*4+4));
    return panel('Overtime planning · daily and shift estimates',`<p>${warehouseRole(run.role)?'Warehouse demand uses saved daily volume ÷ volume per FTE per paid shift, distributed by shift shares.':'Minimum daily headcount is distributed across shifts using whole-person rounding.'} Scheduled demand and make-up staff both count toward capacity.</p><div class="actions">${badge(known.length?f(total,2)+' suggested staff-hours':'No overtime suggested',known.length&&total>0?'warn':'')}${badge('Volume unit: '+(run.overtime?.unit||'units'))}</div><div class="tablewrap"><table><thead><tr><th>Date / day</th><th>Basis / input status</th>${(run.shiftStarts||STARTS).map(s=>'<th>'+timeLabel(s)+'<small>Scheduled / required · OT hours</small></th>').join('')}<th>Daily OT hours</th></tr></thead><tbody>${days.map(rs=>`<tr><td>${rs[0].date}<small>${rs[0].day}</small></td><td>${esc(rs[0].status)}<small>${warehouseRole(run.role)?'Daily volume: '+(run.overtime?.volumes?.[DAYS.indexOf(rs[0].day)]??'Not entered')+' · capacity/FTE: '+(run.overtime?.capacity??'Not set'):'Min daily HC: '+(run.overtime?.minimum??'Not set')}</small></td>${rs.map(r=>`<td class="${r.hours>0?'gap':''}">${r.staff} / ${r.required===null?'—':f(r.required,2)}<small>${r.hours===null?'No suggestion':f(r.hours,2)+'h suggested'}</small></td>`).join('')}<td>${rs.some(r=>r.hours!==null)?f(rs.reduce((n,r)=>n+(r.hours||0),0),2)+'h':'—'}</td></tr>`).join('')}</tbody></table></div><p class="note">Additional staff-hours = max(required FTE − scheduled staff, 0) × paid hours per shift; totals sum shift deficits, without offsetting surplus staff on another shift. Figures are rounded up to 0.01 hour per shift. These are coverage estimates, not employee overtime assignments or approvals. Existing schedule and rest constraints are unchanged. Missing configuration or volume suppresses suggestions; a closed day with volume requires calendar review. Saved estimates use the configuration captured when generated.</p>`)
}
function overtimeSettingsPanel(){
    if(!membershipFeatureEnabled('overtimeForecasting'))return panel('Overtime forecasting','<p>Overtime forecasting is included with Gold and above.</p>');
    let o=overtimeConfig(),locations=[...new Set(model.pools.filter(p=>warehouseRole(p.role)).map(p=>p.location))];
    return panel('Warehouse FTE volume capacity',`<p>Set the average volume one warehouse FTE handles during one normal paid shift. Leave blank or enter 0 to disable volume-based overtime suggestions for that location. This applies only to the Warehouse role, not warehouse supervisors.</p><label>Volume unit · use the same unit for capacity and daily volumes<input type="text" maxlength="40" value="${esc(o.unit)}" data-ot-unit ${disabled()}></label><div class="tablewrap"><table><thead><tr><th>Location</th><th>Average volume / FTE / paid shift</th><th>Overtime basis</th></tr></thead><tbody>${locations.map(loc=>`<tr><td>${esc(loc)}</td><td><input type="number" min="0" max="1000000000000" step="any" value="${esc(o.capacity[loc]??'')}" data-ot-capacity="${esc(loc)}" ${disabled()} aria-label="Average warehouse volume per FTE for ${esc(loc)}"></td><td>${positiveNumber(o.capacity[loc])?'Volume-based enabled':'Disabled · capacity not set'}</td></tr>`).join('')}</tbody></table></div><p class="note">Unlock in Controls & lock to edit. For other roles, set Min daily HC in Location roles. Capacity settings and weekly volumes are captured with newly generated schedules.</p>`)
}
function volumeConfiguration(){
    if(!membershipFeatureEnabled('overtimeForecasting'))return panel('Overtime forecasting','<p>Daily volume and overtime forecasting are included with Gold and above.</p>');
    let o=overtimeConfig(),pools=model.pools.filter(p=>p.enabled&&warehouseRole(p.role)&&(filterLoc==='All'||p.location===filterLoc)),valid=/^\d{4}-\d{2}-\d{2}$/.test(model.controls.week)&&!Number.isNaN(Date.parse(model.controls.week))&&new Date(model.controls.week+'T00:00:00Z').getUTCDay()===1;
    if(!valid)return panel('Daily warehouse volume · by configured week','<p>Select a valid Monday in Controls & lock to map dated weekly volumes.</p>');
    let rows=[];
    for(let p of pools)for(let w=0;w<scheduleWeeks(model);w++){
        let start=addDays(model.controls.week,w*7),l=model.locations.find(l=>l.name===p.location),r=[...model.results].reverse().find(r=>r.location===p.location&&r.role===p.role&&r.start===start&&r.revision===model.revision),est=r?overtimeEstimate({
            ...r,overtime:overtimeSnapshot(model,p,start),shares:p.shares
        }
        ):null;
        rows.push(`<tr><td>${esc(p.location)}<small>${esc(p.role)}</small><small>${positiveNumber(o.capacity[p.location])?f(o.capacity[p.location],2)+' '+esc(o.unit)+'/FTE':'No FTE capacity · no OT suggestion'}</small></td><td>${start}<small>to ${addDays(start,6)}</small></td>${DAYS.map((day,d)=>{
            let date=addDays(start,d),value=o.volumes[p.location]?.[date]??'',rs=est?.slice(d*4,d*4+4),known=rs?.some(x=>x.hours!==null),hours=known?rs.reduce((s,x)=>s+(x.hours||0),0):null;return `<td><small>${date}${l?.open[d]===0?' · Closed':''}</small><input type="number" min="0" max="1000000000000" step="any" value="${esc(value)}" data-ot-volume="${esc(p.location)}" data-ot-date="${date}" ${disabled()} aria-label="${esc(p.location)} ${date} warehouse volume"><small>${!positiveNumber(o.capacity[p.location])?'Capacity not set':value===''?'Volume not entered':l?.open[d]===0&&Number(value)>0?'Closed day · review META':!r?'Generate schedule for OT estimate':hours===null?'No suggestion':f(hours,2)+'h estimated OT'}</small></td>`
        }
        ).join('')}</tr>`)
    }
    return panel('Daily warehouse volume · by configured week',`<p>Enter volume for each day of every selected Warehouse week. Dates follow Week commencing in Controls. The four shift shares above split each day’s volume; META controls operating days. Volume is used only for Warehouse overtime estimates.</p>${rows.length?`<div class="tablewrap volumetable"><table><thead><tr><th>Location / capacity</th><th>Week period</th>${DAYS.map(d=>'<th>'+d+' volume</th>').join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`:'<p>Enable a Warehouse location-role pool above to map its weekly daily volumes.</p>'}<p class="note">Leave a day blank for no volume estimate. Enter 0 for an explicitly zero-volume day. Settings → Warehouse FTE volume capacity sets the per-location denominator. Suggestions compare each shift’s required FTE with actual scheduled staff; generate again after updating configuration to save the new estimates.</p>`)
}
function overtimeRows(runs){
    let a=[['Week commencing','Week ending','Location','Role','Revision','Date','Day','Shift','Basis','Status','Volume unit','Shift volume','Volume per FTE per paid shift','Minimum daily headcount','Required FTE / HC','Scheduled staff','Additional FTE / HC','Suggested OT staff-hours','Paid hours per shift']];
    for(let r of runs)for(let x of overtimeEstimate(r))a.push([r.start,r.end,r.location,r.role,r.revision,x.date,x.day,timeLabel(x.start),x.basis,x.status,r.overtime?.unit??'',x.volume,x.capacity,x.minimum,x.required,x.staff,x.short,x.hours,r.controls.hours]);
    return a
}
function overtimeInputTables(){
    let o=overtimeConfig(),capacity=[['Location','Warehouse volume per FTE per paid shift','Volume unit']],minimum=[['Location','Role','Minimum daily headcount']],volumes=[['Location','Date','Daily warehouse volume','Volume unit']];
    for(let l of [...new Set(model.pools.filter(p=>warehouseRole(p.role)).map(p=>p.location))])capacity.push([l,o.capacity[l]??null,o.unit]);
    for(let p of model.pools.filter(p=>!warehouseRole(p.role)))minimum.push([p.location,p.role,o.minimum[p.id]??null]);
    for(let [l,dates] of Object.entries(o.volumes))for(let [date,value] of Object.entries(dates))volumes.push([l,date,value,o.unit]);
    return {
        'OT FTE Capacity':capacity,'OT Minimum HC':minimum,'OT Daily Volumes':volumes
    }

}
function overtimeInputChange(event){
    let e=event.target;
    if(!membershipFeatureEnabled('overtimeForecasting'))return;
    if(!model||!e.dataset)return;
    let field=e.hasAttribute?.('data-ot-unit')?'unit':e.dataset.otCapacity!==undefined?'capacity':e.dataset.otMinimum!==undefined?'minimum':e.dataset.otVolume!==undefined?'volume':null;
    if(!field)return;
    if(model.locked){
        message('Unlock settings in Controls before changing overtime configuration.',true);
        render(true);
        return
    }
    let o=overtimeConfig();
    if(field==='unit'){
        let v=e.value.trim();
        if(!v){
            message('Enter a volume unit label.',true);
            render(true);
            return
        }
        o.unit=v.slice(0,40)
    }
    else{
        let v=e.value===''?null:Number(e.value);
        if(v!==null&&(!Number.isFinite(v)||v<0||v>1e12||field==='minimum'&&!Number.isInteger(v))){
            message('Enter a non-negative '+(field==='minimum'?'whole headcount':'volume')+' within the allowed range.',true);
            render(true);
            return
        }
        if(field==='capacity')o.capacity[e.dataset.otCapacity]=v;
        if(field==='minimum')o.minimum[e.dataset.otMinimum]=v;
        if(field==='volume'){
            let loc=e.dataset.otVolume,date=e.dataset.otDate;
            if(!o.volumes[loc])o.volumes[loc]={

            }
            ;
            if(v===null)delete o.volumes[loc][date];
            else o.volumes[loc][date]=v
        }

    }
    model.previousScheduleSet=null;
    queueSave();
    if(page==='pools')refreshConfigurationIndicators();
    else render(true)
}
document.addEventListener('change',overtimeInputChange);
function overtimeIssues(m){
    let o=m.overtime;
    if(o===undefined||o===null)return [];
    if(typeof o!=='object'||Array.isArray(o))return ['Overtime configuration must be an object'];
    let errors=[];
    function validValue(v,integer=false){
        return v===null||v===''||isNum(v)&&Number(v)>=0&&Number(v)<=1e12&&(!integer||Number.isInteger(Number(v)))
    }
    for(let k of ['capacity','minimum','volumes']){
        let map=o[k];
        if(map===undefined)continue;
        if(!map||typeof map!=='object'||Array.isArray(map)){
            errors.push('Overtime '+k+' mapping is invalid');
            continue
        }
        for(let [id,value] of Object.entries(map)){
            if(k!=='volumes'){
                if(!validValue(value,k==='minimum'))errors.push('Overtime '+k+': invalid value for '+id)
            }
            else if(!value||typeof value!=='object'||Array.isArray(value))errors.push('Overtime daily volumes: invalid mapping for '+id);
            else for(let [date,v] of Object.entries(value)){
                let dateValid=/^\d{4}-\d{2}-\d{2}$/.test(date)&&!Number.isNaN(Date.parse(date+'T00:00:00Z'))&&new Date(date+'T00:00:00Z').toISOString().slice(0,10)===date;
                if(!dateValid||!validValue(v))errors.push('Overtime daily volume: invalid date or value for '+id+' '+date)
            }

        }

    }
    return errors
}
function scheduleFingerprint(r){
    return JSON.stringify(r.employees.map(e=>[e.id,e.slots]).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))))
}
function refreshBaseline(m){
    if(!m.locked)throw Error('Lock the configuration before refreshing schedules.');
    if(!m.results.length)throw Error('Generate schedules before refreshing.');
    return m.results
}
function noWorseSchedule(r,b){
    return !validateRun(r).length&&r.uncovered.length<=b.uncovered.length&&r.shortages.reduce((n,e)=>n+e.missing,0)<=b.shortages.reduce((n,e)=>n+e.missing,0)
}
function addRunHistory(history,r){
    let abs=Date.parse(r.start+'T00:00:00Z')/36e5;
    for(let e of r.employees){
        let last=history.get(e.id)??-Infinity;
        e.slots.forEach((s,d)=>{
            if(s!==null)last=Math.max(last,abs+d*24+s+r.controls.span)
        }
        );
        if(Number.isFinite(last))history.set(e.id,last)
    }

}
function boundaryValid(r,next){
    if(!next)return true;
    let ends=new Map();
    addRunHistory(ends,r);
    let abs=Date.parse(next.start+'T00:00:00Z')/36e5;
    for(let e of next.employees)for(let d=0;d<7;d++){
        if(e.timeOff?.[d]&&ends.has(e.id)&&ends.get(e.id)>abs+d*24)return false;
        if(e.slots[d]!==null&&ends.has(e.id)&&abs+d*24+e.slots[d]-ends.get(e.id)<next.controls.rest)return false
    }
    return true
}
function validateScheduleSequence(runs){
    let issues=[];
    for(let i=0;i<runs.length;i++){
        issues.push(...validateRun(runs[i]));
        if(!boundaryValid(runs[i],runs[i+1]))issues.push('Rest across saved weeks')
    }
    return issues
}
async function refreshSchedules(){
    let originalResults=refreshBaseline(model);
    busy=true;
    await prepareSchedulingTimeOff([...originalResults.map(r=>r.start),model.controls.week].sort()[0],originalResults.map(r=>r.end).sort().at(-1));
    let baseline=originalResults.map(refreshedTimeOffRun);
    message('Shuffling every saved schedule using its saved configuration and cross-week constraints…');
    let groups=new Map();
    for(let r of baseline){
        let k=r.revision+'|'+key(r.location,r.role)+'|'+(r.importBatch||'generated');
        if(!groups.has(k))groups.set(k,[]);
        groups.get(k).push(r)
    }
    let replacements=new Map(),changed=0,master=randomShuffleSeed(model.controls.seed),processed=0;

    for(let group of groups.values()){
        group.sort((a,b)=>a.start.localeCompare(b.start));
        let history=new Map(),revised=[];
        for(let i=0;i<group.length;i++){
            let b=group[i],chosen=b,context={
                controls:{
                    ...b.controls,shuffle:true
                }
                ,roster:clone(b.roster),locations:[clone(b.locationPattern)],revision:b.revision,requirementsOverride:b.requirements,bambooTimeOff:model.bambooTimeOff,timeOffOverride:Object.fromEntries(b.employees.map(e=>[e.id,e.timeOff||Array(8).fill(false)]))
            }
            ,pool={
                id:key(b.location,b.role),location:b.location,role:b.role,shiftStarts:clone(b.shiftStarts||STARTS),shares:clone(b.shares)
            }
            ;
            for(let attempt=0;attempt<32;attempt++){
                if(attempt%8===0)await new Promise(resolve=>setTimeout(resolve,0));
                context.controls.seed=shuffleRank(master,b.id+'|'+attempt)%1000000;
                let trialHistory=new Map(history),candidate=generatePool(context,pool,b.start,trialHistory);
                if(noWorseSchedule(candidate,b)&&boundaryValid(candidate,group[i+1])&&scheduleFingerprint(candidate)!==scheduleFingerprint(b)){
                    chosen={
                        ...candidate,imported:b.imported,importBatch:b.importBatch,sourceName:b.sourceName,importWarnings:b.importWarnings,tradeHistory:b.tradeHistory,overtime:clone(b.overtime??null),id:b.id,refreshedAt:new Date().toISOString(),shuffleCount:(b.shuffleCount||0)+1
                    }
                    ;
                    break
                }

            }
            if(chosen!==b)changed++;
            revised.push(chosen);
            replacements.set(b.id,chosen);
            addRunHistory(history,chosen);
            processed++;
            if(processed%8===0)message('Shuffling all saved schedules: '+processed+' of '+baseline.length+' checked…')
        }
        let failures=validateScheduleSequence(revised);
        if(failures.length)throw Error('Shuffle validation failed; previous schedules retained: '+failures.join('; '))
    }

    let timeOffChanged=JSON.stringify(baseline.map(r=>r.employees.map(e=>[e.timeOff,e.slots])))!==JSON.stringify(originalResults.map(r=>r.employees.map(e=>[e.timeOff,e.slots])));
    if(!changed&&!timeOffChanged){
        message('All '+baseline.length+' saved schedules checked. No different allocation meeting the saved constraints and coverage/shortfall levels was found in 32 attempts per schedule. Existing schedules retained.'+timeOffSummary(),(model.bambooTimeOff?.status==='error'||model.bambooTimeOff?.apiStatus==='error'));
        return
    }

    let original=model;
    model={
        ...model,controls:{
            ...model.controls,shuffle:true,seed:master
        }
        ,previousScheduleSet:{
            results:originalResults,controls:original.controls,at:new Date().toISOString()
        }
        ,results:baseline.map(r=>replacements.get(r.id))
    }
    ;
    try{
        await saveState()
    }
    catch(e){
        model=original;
        throw e
    }
    page='schedules';
    render();
    message('All '+baseline.length+' saved schedules processed: '+changed+' shuffled; '+(baseline.length-changed)+' retained where no different acceptable allocation was found. Saved configuration constraints, cross-week rest, coverage and employee targets preserved. Undo last shuffle is available.'+(storageMode==='session'?' Session only: download the portable ZIP bundle when hosted or a workspace backup.':'')+timeOffSummary(),(model.bambooTimeOff?.status==='error'||model.bambooTimeOff?.apiStatus==='error'))
}
async function undoShuffle(){
    if(!model.previousScheduleSet)throw Error('No previous shuffle to undo.');
    let original=model;
    model={
        ...model,results:model.previousScheduleSet.results,controls:model.previousScheduleSet.controls,previousScheduleSet:null
    }
    ;
    try{
        await saveState()
    }
    catch(e){
        model=original;
        throw e
    }
    render();
    message('Previous schedules restored. The last shuffle was undone.')
}
let scheduleLocation='All',scheduleRole='All',scheduleWeek='All',scheduleOrigin='All';
function runSeriesKey(r){
    return key(r.location,r.role)+'|'+r.revision+'|'+(r.importBatch||'generated')
}
function visibleScheduleRuns(){
    return model.results.filter(r=>(scheduleLocation==='All'||r.location===scheduleLocation)&&(scheduleRole==='All'||r.role===scheduleRole)&&(scheduleWeek==='All'||r.start===scheduleWeek)&&(scheduleOrigin==='All'||(r.imported?'Uploaded':'Generated')===scheduleOrigin))
}
function scheduleFilters(){
    let all=model.results;
    return `<div class="toolbar"><label>Location ${select([['All','All locations'],...[...new Set(all.map(r=>r.location))].sort().map(v=>[v,v])],scheduleLocation,'id="scheduleLocation"')}</label><label>Role ${select([['All','All roles'],...[...new Set(all.map(r=>r.role))].sort().map(v=>[v,v])],scheduleRole,'id="scheduleRole"')}</label><label>Week ${select([['All','All weeks'],...[...new Set(all.map(r=>r.start))].sort().map(v=>[v,v+' to '+addDays(v,6)])],scheduleWeek,'id="scheduleWeek"')}</label><label>Source ${select([['All','All sources'],['Generated','Generated'],['Uploaded','Uploaded']],scheduleOrigin,'id="scheduleOrigin"')}</label></div>`
}
function bindScheduleFilters(){
    for(let [id,set] of [['scheduleLocation',v=>scheduleLocation=v],['scheduleRole',v=>scheduleRole=v],['scheduleWeek',v=>scheduleWeek=v],['scheduleOrigin',v=>scheduleOrigin=v]])$(id)?.addEventListener('change',e=>{
        set(e.target.value);render()
    }
    )
}
let scheduleRegisterObserver=null,tenantAuthTenantId='',tenantAuthPrimaryAdmin=false;
async function authorizeDataSettings(operation){
    try{
        const result=await directoryRequest('/workspace/data-settings',operation?{
            method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
            body:JSON.stringify({operation,tenantId:tenantAuthTenantId})
        }:{cache:'no-store'});
        if(result.authorized!==true||result.tenantId!==tenantAuthTenantId)throw Error('Primary administrator authorization changed. Reload before continuing.');
        tenantAuthPrimaryAdmin=true;
    }
    catch(error){
        tenantAuthPrimaryAdmin=false;
        pendingSourceImport=null;
        for(const id of ['sourcePickerDialog','sourceImportReviewDialog'])if($(id)?.open)$(id).close();
        render();
        throw error
    }
}
function sizeScheduleRegister(){
    scheduleRegisterObserver?.disconnect();
    const wrapper=$('savedScheduleRegister');
    if(!wrapper)return;
    const table=wrapper.querySelector('table');
    const resize=()=>{
        const rows=[...table.tBodies[0].rows];
        if(rows.length<=6){wrapper.style.maxHeight='none';return;}
        const bottom=rows[5].getBoundingClientRect().bottom-table.getBoundingClientRect().top;
        wrapper.style.maxHeight=Math.floor(bottom)+'px';
    };
    scheduleRegisterObserver=new ResizeObserver(resize);
    scheduleRegisterObserver.observe(table);
    resize()
}
async function deleteSavedSchedule(id){
    const run=model.results.find(item=>item.id===id);
    if(!run)throw Error('Saved schedule not found. Refresh the register.');
    if(storageMode!=='persistent')throw Error('Deletion requires working browser storage. Save a backup and restore browser storage before deleting.');
    if(!confirm(`Delete the browser-saved schedule ${run.start} to ${run.end} · ${run.location} · ${run.role} · revision ${run.revision}?\n\nOnly this workspace copy will be removed. Accepted database copies, BambooHR shifts and existing audit history will NOT be deleted. This cannot be undone through shuffle undo.`))return;
    const authorization=await directoryRequest('/workspace/schedule-deletions',{
        method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
        body:JSON.stringify({runId:id,tenantId:tenantAuthTenantId,scope:'browser-workspace'})
    });
    if(authorization.authorized!==true)throw Error('Schedule deletion was not authorized.');
    const results=model.results.filter(item=>item.id!==id);
    const next={...model,results,previousScheduleSet:null,
        selectedRun:model.selectedRun===id?(results[0]?.id||''):model.selectedRun,
        scheduleDeletionHistory:[...(model.scheduleDeletionHistory||[]),{
            runId:id,deletedAt:new Date().toISOString(),actor:model.user?.email||'',
            tenantId:tenantAuthTenantId,scope:'browser-workspace'
        }]};
    clearTimeout(saveTimer);
    try{await store('put',next);}
    catch(error){throw Error('Schedule was not deleted: browser storage failed. '+error.message);}
    model=next;
    if(scheduleLocation!=='All'&&!results.some(item=>item.location===scheduleLocation))scheduleLocation='All';
    if(scheduleRole!=='All'&&!results.some(item=>item.role===scheduleRole))scheduleRole='All';
    if(scheduleWeek!=='All'&&!results.some(item=>item.start===scheduleWeek))scheduleWeek='All';
    if(scheduleOrigin!=='All'&&!results.some(item=>(item.imported?'Uploaded':'Generated')===scheduleOrigin))scheduleOrigin='All';
    if($('emailDialog')?.open)$('emailDialog').close();
    preparedEmailGeneration++;preparedEmail=null;
    render();
    message('Browser-saved schedule deleted. Accepted database copies and BambooHR shifts were not changed.')
}
function rebuildScheduleAudit(r){
    let old=new Map((r.audit||[]).map(x=>[x.id+'|'+x.day+'|'+x.start,x]));
    r.audit=[];
    for(let e of r.employees)e.slots.forEach((s,d)=>{
        if(s!==null)r.audit.push(old.get(e.id+'|'+d+'|'+s)||{
            id:e.id,day:d,start:s,type:e.types[d]||'Demand',score:null
        }
        )
    }
    );
    r.primary=r.audit.filter(a=>a.type==='Demand').length;
    r.makeup=r.audit.filter(a=>a.type==='Make-up').length;
    r.shortages=r.employees.filter(e=>e.slots.filter(s=>s!==null).length<r.controls.shifts).map(e=>({
        id:e.id,name:e.name,missing:r.controls.shifts-e.slots.filter(s=>s!==null).length
    }
    ));
    return r
}
function tradePlan(runId,firstId,secondId,days){
    let r=model.results.find(r=>r.id===runId),errors=[];
    if(!r)return {
        errors:['Choose a saved location, role and week.']
    }
    ;
    let first=r.employees.find(e=>e.id===firstId),second=r.employees.find(e=>e.id===secondId);
    if(!first||!second||firstId===secondId)return {
        errors:['Select two different employees in this location and role.']
    }
    ;
    days=[...new Set(days.map(Number))].sort();
    if(!days.length||days.some(d=>!Number.isInteger(d)||d<0||d>6))return {
        errors:['Select one or more days.']
    }
    ;
    let next=clone(r);
    if(typeof timeOffDays==='function')for(let e of next.employees){
        let live=timeOffDays(model,e,r.start);
        e.timeOff=Array.from({
            length:8
        }
        ,(_,d)=>!!e.timeOff?.[d]||live[d])
    }
    let a=next.employees.find(e=>e.id===firstId),b=next.employees.find(e=>e.id===secondId);
    for(let d of days){
        [a.slots[d],b.slots[d]]=[b.slots[d],a.slots[d]];
        [a.types[d],b.types[d]]=[b.types[d],a.types[d]]
    }
    let ca=a.slots.filter(s=>s!==null).length,cb=b.slots.filter(s=>s!==null).length;
    if(ca!==5||cb!==5)errors.push('Both employees must finish with exactly 5 working days. Current preview: '+a.name+' '+ca+', '+b.name+' '+cb+'. Include a balancing day where the other employee is OFF.');
    if(days.every(d=>first.slots[d]===second.slots[d]))errors.push('The selected days do not change either employee’s shifts.');
    rebuildScheduleAudit(next);
    errors.push(...validateRun(next));
    let series=model.results.filter(x=>x.id!==r.id&&runSeriesKey(x)===runSeriesKey(r)).sort((a,b)=>a.start.localeCompare(b.start)),prior=series.filter(x=>x.start<r.start).at(-1),following=series.find(x=>x.start>r.start);
    if(prior&&!boundaryValid(prior,next))errors.push('The trade breaks minimum rest after the previous saved week.');
    if(following&&!boundaryValid(next,following))errors.push('The trade breaks minimum rest before the next saved week.');
    if(!prior){
        let abs=Date.parse(r.start+'T00:00:00Z')/36e5;
        for(let e of [a,b]){
            let d=e.slots.findIndex(s=>s!==null);
            if(d>=0&&e.previous!==null&&e.previous!==-1&&abs+d*24+e.slots[d]-(abs-24+e.previous+r.controls.span)<r.controls.rest)errors.push('The trade breaks prior-Sunday rest for '+e.name+'.')
        }

    }
    return {
        errors:[...new Set(errors)],original:r,next,first,second,days,counts:[ca,cb]
    }

}
function tradeSelection(){
    return {
        runId:$('tradeWeek').value,firstId:$('tradeFirst').value,secondId:$('tradeSecond').value,days:[...$('tradeDialog').querySelectorAll('[data-trade-day]:checked')].map(e=>+e.value)
    }

}
function updateTradePreview(){
    let s=tradeSelection(),p=tradePlan(s.runId,s.firstId,s.secondId,s.days);
    $('confirmTrade').hidden=p.errors.length>0;
    $('tradeStatus').innerHTML=p.errors.length?'<ul>'+p.errors.map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul>':'<p class="goodtext">Both employees retain five working days. Scheduling checks passed. You can confirm the trade.</p>';
    let r=model.results.find(r=>r.id===s.runId),a=r?.employees.find(e=>e.id===s.firstId),b=r?.employees.find(e=>e.id===s.secondId);
    if(!a||!b||a===b){
        $('tradeDays').innerHTML='';
        return
    }
    let fmt=(s,e,d)=>s===null?(e.timeOff?.[d]?'time-off':'OFF'):timeLabel(s);
    $('tradeDays').innerHTML=`<div class="tablewrap"><table><thead><tr><th>Select</th><th>Day / date</th><th>${esc(a.name)}<small>Before → after</small></th><th>${esc(b.name)}<small>Before → after</small></th></tr></thead><tbody>${DAYS.map((day,d)=>`<tr><td><input type="checkbox" data-trade-day value="${d}" ${s.days.includes(d)?'checked':''} aria-label="Trade ${day}"></td><td>${day}<small>${addDays(r.start,d)}</small></td><td>${fmt(a.slots[d],a,d)} → <b>${fmt(s.days.includes(d)?b.slots[d]:a.slots[d],a,d)}</b></td><td>${fmt(b.slots[d],b,d)} → <b>${fmt(s.days.includes(d)?a.slots[d]:b.slots[d],b,d)}</b></td></tr>`).join('')}</tbody></table></div>`
}
function tradeWeekChanged(){
    let r=model.results.find(r=>r.id===$('tradeWeek').value);
    $('tradeFirstWrap').innerHTML='Employee 1 '+select([['','Select employee'],...(r?.employees||[]).map(e=>[e.id,e.name+' · '+e.id])],'','id="tradeFirst"');
    $('tradeSecondWrap').innerHTML='Employee 2 '+select([['','Select employee'],...(r?.employees||[]).map(e=>[e.id,e.name+' · '+e.id])],'','id="tradeSecond"');
    $('tradeDays').innerHTML='';
    updateTradePreview()
}
function tradePoolChanged(){
    let rs=model.results.filter(r=>key(r.location,r.role)===$('tradePool').value);
    $('tradeWeekWrap').innerHTML='Week / saved version '+select(rs.map(r=>[r.id,r.start+' to '+r.end+' · rev '+r.revision+(r.imported?' · Uploaded':'')]),rs.find(r=>r.id===model.selectedRun)?.id||rs[0]?.id,'id="tradeWeek"');
    tradeWeekChanged()
}
function openTrades(){
    if(!membershipFeatureEnabled('shiftTrades'))throw Error('Shift trades are included with Silver and above.');
    return TradePicker.open({
        base:'/api/shift-trades',
        api:(path,method='GET',body)=>directoryRequest(path.slice(4),{
            method,headers:{'X-CSRF-Token':tenantAuthCsrfToken},
            ...(body===undefined?{}:{body:JSON.stringify(body)})
        }),
        onCreated:()=>message('Trade submitted. Open the shift trade inbox to review approvals.')
    })
}
async function confirmShiftTrade(){
    throw Error('Use the authenticated shift trade inbox to request, approve and apply trades.')
}
function tradeLogRows(runs){
    let a=[['Confirmed at','Week commencing','Location','Role','Revision','Employee 1 ID','Employee 1','Employee 2 ID','Employee 2','Traded days']];
    for(let r of runs)for(let t of r.tradeHistory||[])a.push([t.at,t.week,r.location,r.role,r.revision,t.firstId,t.firstName,t.secondId,t.secondName,t.days.map(d=>DAYS[d]).join(', ')]);
    return a
}
document.addEventListener('change',e=>{
    if(e.target.id==='tradePool')tradePoolChanged();else if(e.target.id==='tradeWeek')tradeWeekChanged();else if(['tradeFirst','tradeSecond'].includes(e.target.id)||e.target.dataset?.tradeDay!==undefined)updateTradePreview()
}
);
document.addEventListener('click',async e=>{
    let cmd=e.target.closest('[data-trade-command]')?.dataset.tradeCommand;if(!cmd||busy)return;try{
        if(cmd==='close')$('tradeDialog').close();else if(cmd==='confirm')await confirmShiftTrade()
    }
    catch(err){
        $('tradeStatus').textContent=err.message
    }

}
);
function parseScheduleShift(value,span=9,starts=STARTS){
    if(value===null||value===undefined||String(value).trim()==='')return null;
    if(typeof value==='number'){
        let s=starts.includes(value)?value:value>=0&&value<1?Math.round(value*24*100)/100:NaN;
        if(starts.includes(s))return s;
        throw Error('Unsupported numeric shift '+value)
    }
    let text=String(value).trim();
    if(/^(off|time[ -]off|day\s*off|rest|rdo|-)$/i.test(text))return null;
    let clean=text.replace(/\s*\(\+1d\)/ig,'').replace(/\s*\+\s*$/,'').trim(),parts=clean.split(/\s*[–—-]\s*/);
    function hour(t){
        let m=t.trim().match(/^(\d{1,2})(?::(\d{2})(?::\d{2})?)?\s*(AM|PM)?$/i);
        if(!m)return NaN;
        let h=+m[1],minute=+(m[2]||0),amp=m[3]?.toUpperCase();
        if(minute>59||amp&&(h<1||h>12)||!amp&&h>23)return NaN;
        if(amp)h=h%12+(amp==='PM'?12:0);
        return h+minute/60
    }
    let start=hour(parts[0]);
    if(!starts.includes(start))throw Error('Unsupported shift "'+text+'". Add '+timeLabel(start)+' to the location-role shift settings first.');
    if(parts.length>1){
        let end=hour(parts[1]);
        if(!Number.isFinite(end)||Math.abs(((end-start+24)%24||24)-span)>1e-6)throw Error('Shift end time does not match the configured elapsed span: '+text)
    }
    return start
}
function scheduleImportRows(db,defaults){
    let sheet=db['Weekly Schedules']||db.Schedule||Object.values(db).find(a=>a.some(r=>r.some(c=>String(c).trim().toLowerCase()==='mon')));
    if(!sheet)throw Error('No weekly schedule table found. Download and use the schedule template.');
    let norm=v=>String(v??'').trim().toLowerCase().replace(/[._]/g,' ').replace(/\s+/g,' '),headerIndex=sheet.findIndex(r=>r.some(v=>norm(v)==='mon')&&r.some(v=>['employee','employee name','name'].includes(norm(v))));
    if(headerIndex<0)throw Error('Expected Employee and Mon–Sun column headers.');
    let h=sheet[headerIndex].map(norm),col=(...names)=>names.map(n=>h.indexOf(n)).find(i=>i>=0)??-1,index={
        week:col('week commencing','week commencing date','week start'),location:col('location'),role:col('role','team'),id:col('employee id','id'),name:col('employee','employee name','name'),hours:col('paid hours per shift'),span:col('shift span hours','elapsed span'),rest:col('minimum rest hours','rest hours')
    }
    ,dayCols=DAYS.map(d=>col(d.toLowerCase()));
    if(dayCols.some(i=>i<0))throw Error('All seven Mon–Sun columns are required.');
    let fallback=model.pools.find(p=>p.id===defaults.pool),groups=new Map(),seen=new Set(),warnings=[];

    for(let i=headerIndex+1;i<sheet.length;i++){
        let row=sheet[i];
        if(!row||row.every(v=>v===null||v===undefined||v===''))continue;
        let get=k=>index[k]>=0?row[index[k]]:null,rawName=String(get('name')??'').trim(),rawId=String(get('id')??'').trim();
        if(!rawName&&!rawId)continue;
        let location=String(get('location')??'').trim()||fallback?.location,role=String(get('role')??'').trim()||fallback?.role,week=isoDate(get('week')||defaults.week);
        if(!location||!role)throw Error('Row '+(i+1)+': provide Location and Role, or choose a fallback location/team.');
        if(!/^\d{4}-\d{2}-\d{2}$/.test(week)||Number.isNaN(Date.parse(week+'T00:00:00Z'))||new Date(week+'T00:00:00Z').toISOString().slice(0,10)!==week||new Date(week+'T00:00:00Z').getUTCDay()!==1)throw Error('Row '+(i+1)+': Week commencing must be a valid Monday.');
        let profile=rawId?model.roster.find(e=>e.id===rawId):null;
        if(!rawId){
            let matches=model.roster.filter(e=>e.name.trim().toLowerCase()===rawName.toLowerCase()&&e.location===location&&e.role===role);
            if(matches.length>1)throw Error('Row '+(i+1)+': ambiguous employee name; supply Employee ID.');
            profile=matches[0]
        }

        if(profile&&(profile.location!==location||profile.role!==role))throw Error('Row '+(i+1)+': employee ID belongs to a different location/team in the roster.');
        let name=rawName||profile?.name;
        if(!name)throw Error('Row '+(i+1)+': Employee name is required.');
        let id=rawId||profile?.id||'upload:'+key(location,role)+':'+name.toLowerCase(),duplicate=week+'|'+id;
        if(seen.has(duplicate))throw Error('Row '+(i+1)+': duplicate employee/week. Include only one schedule version for each employee/week.');
        seen.add(duplicate);
        let supplied=k=>get(k)!==null&&get(k)!==undefined&&get(k)!==''?get(k):undefined,controlRows=db.Controls||[],ch=controlRows[0]||[],saved=controlRows.slice(1).find(r=>String(r[ch.indexOf('Location')])===location&&String(r[ch.indexOf('Role')])===role&&isoDate(r[ch.indexOf('Week commencing')])===week),savedValue=label=>saved?.[ch.indexOf(label)],hours=Number(supplied('hours')??savedValue('Paid hours')??defaults.hours),span=Number(supplied('span')??savedValue('Elapsed span')??defaults.span),rest=Number(supplied('rest')??savedValue('Rest hours')??defaults.rest);
        if(!(hours>0&&hours<=24&&span>=hours&&span<=24&&rest>=0&&rest<=48))throw Error('Row '+(i+1)+': invalid paid hours, elapsed span or rest hours.');
        let slots;
        try{
            slots=dayCols.map(j=>parseScheduleShift(row[j],span,poolStarts(model.pools.find(p=>p.location===location&&p.role===role))))
        }
        catch(e){
            throw Error('Row '+(i+1)+': '+e.message)
        }
        let configuredStarts=poolStarts(model.pools.find(p=>p.location===location&&p.role===role)),fullProfile=profile&&profile.days.every(v=>v===0||v===1)&&['Yes','No'].includes(profile.flex)&&configuredStarts.includes(profile.preferred)&&configuredStarts.every(s=>[0,1].includes(employeeStartPermission(profile,s)));
        if(!fullProfile)warnings.push(name+' ('+location+' / '+role+'): roster availability or shift constraints are incomplete or unavailable.');
        let e={
            ...clone(profile||{

            }
            ),id,name,location,role,index:i,flex:profile?.flex==='No'&&STARTS.includes(profile.preferred)?'No':'Yes',reason:profile?.reason||'',preferred:STARTS.includes(profile?.preferred)?profile.preferred:slots.find(s=>s!==null)??6,proximity:profile?.proximity||1,random:profile?.random||1,attendance:profile?.attendance??null,allow:Array.from({
                length:4
            }
            ,(_,j)=>profile?(employeeStartPermission(profile,STARTS[j])??0):1),days:Array.from({
                length:7
            }
            ,(_,j)=>[0,1].includes(profile?.days[j])?profile.days[j]:1),previous:week===model.controls.week?profile?.previous??-1:-1,timeOff:dayCols.map(j=>/^time[ -]off$/i.test(String(row[j]??'').trim())),manualTimeOff:dayCols.map(j=>/^time[ -]off$/i.test(String(row[j]??'').trim())),slots,types:slots.map(s=>s===null?null:'Demand'),rank:0,constraintsKnown:!!fullProfile
        }
        ;
        if(profile&&configuredStarts.includes(profile.preferred)){
            e.preferred=profile.preferred;
            e.flex=profile.flex
        }
        e.shiftAvailability=Object.fromEntries(configuredStarts.map(s=>[String(s),profile?employeeCanStart(profile,s):slots.includes(s)?1:0]));
        let k=key(location,role)+'|'+week;
        if(!groups.has(k))groups.set(k,{
            location,role,week,hours,span,rest,employees:[]
        }
        );
        let g=groups.get(k);
        if(g.hours!==hours||g.span!==span||g.rest!==rest)throw Error('Row '+(i+1)+': hours and rest must match other employees in this location/team/week.');
        g.employees.push(e)
    }
    if(!groups.size)throw Error('No employee schedule rows found.');
    return {
        groups:[...groups.values()],warnings:[...new Set(warnings)]
    }

}
function importScheduleModel(db,defaults,filename){
    let {
        groups,warnings
    }
    =scheduleImportRows(db,defaults),batch='upload-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8),revision=Math.max(model.revision,...model.results.map(r=>r.revision))+1,runs=[];
    for(let g of groups){
        let requirements=DAYS.map((_,d)=>STARTS.map(s=>g.employees.filter(e=>e.slots[d]===s).length)),counts=STARTS.map((_,j)=>requirements.reduce((n,r)=>n+r[j],0)),total=counts.reduce((a,b)=>a+b,0),p=model.pools.find(p=>p.location===g.location&&p.role===g.role),shares=total?counts.map(n=>n/total):p?.shares?.every(isNum)?p.shares:[1,0,0,0],daily=requirements.map(r=>r.reduce((a,b)=>a+b,0)),sourceLocation=model.locations.find(l=>l.name===g.location),locationPattern=sourceLocation?clone(sourceLocation):{
            name:g.location,intensity:daily.map(n=>total?n/total:1/7),open:Array(7).fill(1)
        }
        ,controls={
            ...clone(model.controls),location:g.location,role:g.role,week:g.week,headcount:g.employees.length,shifts:5,hours:g.hours,span:g.span,rest:g.rest,shuffle:false
        }
        ,r={
            id:batch+'|'+key(g.location,g.role)+'|'+g.week,imported:true,importBatch:batch,sourceName:filename,importWarnings:warnings.filter(w=>w.includes('('+g.location+' / '+g.role+')')),location:g.location,role:g.role,start:g.week,end:addDays(g.week,6),revision,createdAt:new Date().toISOString(),controls,shares,locationPattern,roster:g.employees.map(e=>{
                let a=clone(e);delete a.slots;delete a.types;return a
            }
            ),employees:g.employees,requirements,uncovered:[],audit:[],overtime:overtimeSnapshot(model,{
                id:key(g.location,g.role),location:g.location,role:g.role
            }
            ,g.week),tradeHistory:[]
        }
        ;
        rebuildScheduleAudit(r);
        let errors=validateRun(r);
        if(errors.length)throw Error(g.location+' / '+g.role+' / '+g.week+': '+errors.slice(0,8).join('; '));
        runs.push(r)
    }
    let series=new Map();
    for(let r of runs){
        let k=key(r.location,r.role);
        if(!series.has(k))series.set(k,[]);
        series.get(k).push(r)
    }
    for(let rs of series.values()){
        rs.sort((a,b)=>a.start.localeCompare(b.start));
        if(validateScheduleSequence(rs).length)throw Error('Uploaded schedules break rest constraints between weeks.');
        let first=rs[0],abs=Date.parse(first.start+'T00:00:00Z')/36e5;
        for(let e of first.employees){
            let d=e.slots.findIndex(s=>s!==null);
            if(d>=0&&e.previous!==-1&&abs+d*24+e.slots[d]-(abs-24+e.previous+first.controls.span)<first.controls.rest)throw Error('Prior-Sunday rest is not met for '+e.name)
        }

    }
    return {
        runs,warnings
    }

}
function importScheduleModel(db,defaults,filename){
    let {groups,warnings}=scheduleImportRows(db,defaults),batch='upload-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8),revision=Math.max(model.revision,...model.results.map(r=>r.revision))+1,runs=[];
    for(let group of groups){
        let pool=model.pools.find(item=>item.location===group.location&&item.role===group.role),starts=pool?[...poolStarts(pool)]:[...new Set(group.employees.flatMap(employee=>employee.slots.filter(start=>start!==null)))].sort((a,b)=>a-b);
        if(!starts.length)starts=[...STARTS];
        let requirements=DAYS.map((_,day)=>starts.map(start=>group.employees.filter(employee=>employee.slots[day]===start).length)),counts=starts.map((_,index)=>requirements.reduce((total,row)=>total+row[index],0)),total=counts.reduce((sum,count)=>sum+count,0),shares=total?counts.map(count=>count/total):pool?.shares?.every(isNum)?pool.shares:[1,...Array(starts.length-1).fill(0)],daily=requirements.map(row=>row.reduce((sum,count)=>sum+count,0)),sourceLocation=model.locations.find(location=>location.name===group.location),locationPattern=sourceLocation?clone(sourceLocation):{name:group.location,intensity:daily.map(count=>total?count/total:1/7),open:Array(7).fill(1)},controls={...clone(model.controls),location:group.location,role:group.role,week:group.week,headcount:group.employees.length,shifts:5,hours:group.hours,span:group.span,rest:group.rest,shuffle:false},overtimePool=pool||{id:key(group.location,group.role),location:group.location,role:group.role,shares,shiftStarts:starts},run={
            id:batch+'|'+key(group.location,group.role)+'|'+group.week,imported:true,importBatch:batch,sourceName:filename,importWarnings:warnings.filter(warning=>warning.includes('('+group.location+' / '+group.role+')')),location:group.location,role:group.role,shiftStarts:starts,start:group.week,end:addDays(group.week,6),revision,createdAt:new Date().toISOString(),controls,shares,locationPattern,roster:group.employees.map(employee=>{let entry=clone(employee);delete entry.slots;delete entry.types;return entry}),employees:group.employees,requirements,uncovered:[],audit:[],overtime:overtimeSnapshot(model,overtimePool,group.week),tradeHistory:[]
        };
        rebuildScheduleAudit(run);
        let errors=validateRun(run);
        if(errors.length)throw Error(group.location+' / '+group.role+' / '+group.week+': '+errors.slice(0,8).join('; '));
        runs.push(run)
    }
    let series=new Map();
    for(let run of runs){
        let poolKey=key(run.location,run.role);
        if(!series.has(poolKey))series.set(poolKey,[]);
        series.get(poolKey).push(run)
    }
    for(let schedules of series.values()){
        schedules.sort((left,right)=>left.start.localeCompare(right.start));
        if(validateScheduleSequence(schedules).length)throw Error('Uploaded schedules break rest constraints between weeks.');
        let first=schedules[0],absolute=Date.parse(first.start+'T00:00:00Z')/36e5;
        for(let employee of first.employees){
            let day=employee.slots.findIndex(start=>start!==null);
            if(day>=0&&employee.previous!==-1&&absolute+day*24+employee.slots[day]-(absolute-24+employee.previous+first.controls.span)<first.controls.rest)throw Error('Prior-Sunday rest is not met for '+employee.name)
        }
    }
    return {runs,warnings}
}
function openScheduleImport(){
    let d=$('scheduleImportDialog');
    d.innerHTML=`<div class="dialoghead"><h2>Upload weekly schedules</h2><button type="button" data-schedule-import="close" aria-label="Close">✕</button></div><p>Upload the completed schedule template or an app export’s Weekly Schedules sheet. Existing schedules remain saved. Empty shift cells are OFF.</p><label>Schedule workbook · XLSX<input type="file" id="scheduleFile" accept=".xlsx"></label><div class="formgrid"><label>Fallback location × role · blank fields only ${select([['','Use file values'],...model.pools.map(p=>[p.id,p.location+' · '+p.role])],'','id="importDefaultPool"')}</label><label>Fallback Monday · blank dates only<input type="date" id="importDefaultWeek" value="${esc(model.controls.week)}"></label><label>Default paid hours per shift<input type="number" id="importDefaultHours" min="0.5" max="24" step="any" value="${model.controls.hours}"></label><label>Default elapsed span · hours<input type="number" id="importDefaultSpan" min="0.5" max="24" step="any" value="${model.controls.span}"></label><label>Default minimum rest · hours<input type="number" id="importDefaultRest" min="0" max="48" step="any" value="${model.controls.rest}"></label></div><p class="note">Location, Role and Employee fields identify each schedule. Matching employee IDs apply roster restrictions. Unknown or incomplete profiles will be flagged; their unavailable constraints cannot be checked. Uploaded files support all schedule filters, shift trades, email and downloads. Employees may have up to five shifts; trades require exactly five each.</p><p id="scheduleImportStatus" role="status"></p><button type="button" class="primary" data-schedule-import="upload">Validate & import schedules</button>`;
    d.showModal()
}
async function uploadSchedules(){
    let file=$('scheduleFile').files[0];
    if(!file)throw Error('Choose an XLSX schedule workbook.');
    if(file.size>60e6)throw Error('Workbook exceeds 60 MB.');
    let defaults={
        pool:$('importDefaultPool').value,week:$('importDefaultWeek').value,hours:Number($('importDefaultHours').value),span:Number($('importDefaultSpan').value),rest:Number($('importDefaultRest').value)
    }
    ;
    busy=true;
    $('scheduleImportStatus').textContent='Reading and validating schedules…';
    try{
        let db=await parseXlsx(await file.arrayBuffer()),{
            runs,warnings
        }
        =importScheduleModel(db,defaults,file.name),old=model;
        model={
            ...model,results:[...model.results,...runs],selectedRun:runs[0].id,previousScheduleSet:null
        }
        ;
        try{
            await saveState()
        }
        catch(e){
            model=old;
            throw e
        }
        scheduleLocation=scheduleRole=scheduleWeek=scheduleOrigin='All';
        $('scheduleImportDialog').close();
        page='schedules';
        render();
        message(runs.length+' uploaded schedules saved. '+warnings.length+' employee profiles have missing roster constraints; review the notes on each schedule.'+(storageMode==='session'?' Session only: save a backup; hosted apps can also download the portable ZIP bundle.':''))
    }
    finally{
        busy=false
    }

}
async function downloadScheduleTemplate(){
    let raw=Uint8Array.from(atob(SCHEDULE_TEMPLATE_BASE),c=>c.charCodeAt(0)),z=await zipEntries(raw.buffer),files={

    }
    ;
    for(let name of SCHEDULE_TEMPLATE_FILES)files[name]=await z.text(name);
    let pairs=model.pools.map(p=>[p.location,p.role]),locs=[...new Set(pairs.map(p=>p[0]))].sort(),roles=[...new Set(pairs.map(p=>p[1]))].sort(),count=Math.max(locs.length,roles.length,5,pairs.length),listRows=[['Locations','Roles','Shifts','Valid pair location','Valid pair role'],...Array.from({
        length:count
    }
    ,(_,i)=>[locs[i]??'',roles[i]??'',['OFF','6 AM','8:30 AM','2 PM','10 PM'][i]??'',pairs[i]?.[0]??'',pairs[i]?.[1]??''])];
    files['xl/worksheets/sheet2.xml']=sheetXML(listRows);
    files['xl/worksheets/sheet1.xml']=files['xl/worksheets/sheet1.xml'].replace(/Lists!\$A\$2:\$A\$\d+/g,'Lists!$A$2:$A$'+(locs.length+1)).replace(/Lists!\$B\$2:\$B\$\d+/g,'Lists!$B$2:$B$'+(roles.length+1));
    downloadFile('CBL-Weekly-Schedule-Template.xlsx',zipStore(files))
}
document.addEventListener('click',async e=>{
    let cmd=e.target.closest('[data-schedule-import]')?.dataset.scheduleImport;if(!cmd||busy)return;try{
        if(cmd==='close')$('scheduleImportDialog').close();if(cmd==='upload')await uploadSchedules()
    }
    catch(err){
        $('scheduleImportStatus').textContent='Import failed; existing schedules retained. '+err.message
    }

}
);
let localConnectorToken='';
const dismissedHeaderNotices=new Set();
function dismissHeaderNotice(id){
    dismissedHeaderNotices.add(id);
    let wrap=$(id+'Wrap');
    if(wrap)wrap.hidden=true
}
function updateHeaderNotices(){
    for(let id of ['storageWarning','savedState']){
        let w=$(id+'Wrap');
        if(w)w.hidden=dismissedHeaderNotices.has(id)||(id==='storageWarning'&&storageMode!=='session')
    }

}
function normalizedEmployeeName(value){
    return String(value??'').normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim()
}
function validTimeOffDate(v){
    return typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&!Number.isNaN(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v
}
function timeOffDays(m,e,start){
    let manual=e.manualTimeOff||[];
    let entries=m.bambooTimeOff?.status==='success'?m.bambooTimeOff.entries:[];
    return Array.from({
        length:8
    }
    ,(_,d)=>{
        let date=addDays(start,d);return !!manual[d]||entries.some(t=>(t.employeeId?String(t.employeeId)===String(e.bamboohrId):normalizedEmployeeName(t.name)===normalizedEmployeeName(e.name))&&t.start<=date&&t.end>=date)
    }
    )
}
function timeOffCheckSnapshot(m){
    let t=m.bambooTimeOff;
    return t?{
        status:t.status,start:t.start,end:t.end,checkedAt:t.checkedAt,source:t.source||'api',sourceName:t.sourceName||'',apiStatus:t.apiStatus,apiError:t.apiError,error:t.error||'',count:t.entries.length
    }
    :null
}
function timeOffLabel(e,d){
    return e.timeOff?.[d]?'time-off':'OFF'
}
function timeOffSummary(){
    let t=model.bambooTimeOff;
    if(!t)return '';
    if(t.status==='error')return ' BambooHR time-off data unavailable; review this schedule. '+t.error;
    if(t.status==='success')return ' BambooHR time-offs checked for '+t.start+' to '+t.end+' at '+new Date(t.checkedAt).toLocaleString()+'; '+t.entries.length+' employee time-off records received.';
    return ' BambooHR time-off data unavailable; review this schedule.'
}
function basicAuthorization(key,password){
    let bytes=new TextEncoder().encode(key+':'+password),binary='';
    for(let b of bytes)binary+=String.fromCharCode(b);
    return 'Basic '+btoa(binary)
}
async function prepareTimeOff(start,end){
    let state={
        status:'loading',source:'api',start,end,entries:[],checkedAt:new Date().toISOString(),error:''
    }
    ;
    model.bambooTimeOff=state;
    try{
        let response=await fetch('/api/bamboohr/time-offs?'+new URLSearchParams({start,end}),{
            method:'GET',headers:{accept:'application/json'},cache:'no-store'
        });
        let data=await response.json().catch(()=>({}));
        if(!response.ok)throw Error(data.error||'BambooHR time-off request failed with HTTP '+response.status+'.');
        if(!Array.isArray(data.entries))throw Error('BambooHR time-off response is invalid.');
        state.entries=data.entries;
        state.status='success';
        state.start=data.start||start;
        state.end=data.end||end
    }
    catch(err){
        state.status='error';
        state.entries=[];
        state.error=err.message||'BambooHR time-off request failed.'
    }
    state.checkedAt=new Date().toISOString();
    return state
}
async function prepareGenerationTimeOff(){
    if(!model.locked)throw Error('Lock configuration before creating schedules.');
    let check=modelIssues(model);
    if(check.errors.length)throw Error(check.errors.join('; '));
    let weeks=scheduleWeeks(model);
    return prepareSchedulingTimeOff(model.controls.week,addDays(model.controls.week,weeks*7-1))
}
function refreshedTimeOffRun(r){
    let next=clone(r);
    if(model.bambooTimeOff?.status!=='success'){
        next.timeOffCheck=timeOffCheckSnapshot(model);
        return next
    }
    for(let e of next.employees){
        e.timeOff=timeOffDays(model,e,next.start);
        for(let d=0;d<7;d++)if(e.slots[d]!==null&&(e.timeOff[d]||e.slots[d]+next.controls.span>24&&e.timeOff[d+1])){
            e.slots[d]=null;
            e.types[d]=null
        }

    }
    next.timeOffCheck=timeOffCheckSnapshot(model);
    next.uncovered=[];
    for(let d=0;d<7;d++)for(let j=0;j<(next.shiftStarts||STARTS).length;j++){
        let start=(next.shiftStarts||STARTS)[j],got=next.employees.filter(e=>e.slots[d]===start&&e.types[d]==='Demand').length;
        for(let n=got;n<next.requirements[d][j];n++)next.uncovered.push({
            day:d,start,reason:'No eligible employee after time-off exclusions'
        }
        )
    }
    return rebuildScheduleAudit(next)
}
async function clearLegacyBambooCredentials(){
    if(storageMode==='session')return;
    try{
        await store('delete',undefined,'bambooCredentials')
    }
    catch(error){
        message('A previously saved browser BambooHR credential could not be removed: '+error.message,true)
    }

}
function openUserProfile(){
    let name=model.user?.firstName||'',email=model.user?.email||'';
    $('profileDialog').innerHTML=`<div class="dialoghead"><div><div class="eyebrow">${esc(businessConfig.businessName)}</div><h2>Your profile</h2></div><button type="button" data-dialog-close="profileDialog" aria-label="Close profile">✕</button></div><form id="profileForm"><label>Name<input id="profileName" type="text" maxlength="120" required autocomplete="name" value="${esc(name)}"></label><label>Email<input id="profileEmail" type="email" maxlength="254" required autocomplete="email" value="${esc(email)}"></label><label id="profilePasswordLabel" hidden>Current password (required to change email)<input id="profileCurrentPassword" type="password" autocomplete="current-password"></label><p id="profileStatus" role="status"></p><div class="actions"><button class="primary" type="submit">Save profile</button><button type="button" data-dialog-close="profileDialog">Cancel</button></div></form>`;
    const emailInput=$('profileEmail'),passwordLabel=$('profilePasswordLabel'),passwordInput=$('profileCurrentPassword');
    emailInput.addEventListener('input',()=>{
        let changed=emailInput.value.trim().toLowerCase()!==email.toLowerCase();
        passwordLabel.hidden=!changed;
        passwordInput.required=changed
    });
    $('profileForm').addEventListener('submit',async event=>{
        event.preventDefault();
        if(busy)return;
        busy=true;
        try{
            let response=await fetch('/api/business/profile',{
                method:'POST',
                headers:{'Content-Type':'application/json','X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({name:$('profileName').value,email:emailInput.value,currentPassword:passwordInput.value})
            }),result=await response.json();
            if(!response.ok)throw Error(result.error||'Profile update failed.');
            model.user={firstName:result.name,email:result.email};
            $('profileDialog').close();
            $('profileDialog').innerHTML='';
            render();
            message('Profile updated.')
        }catch(error){$('profileStatus').textContent=error.message}
        finally{busy=false}
    });
    $('profileDialog').showModal()
}
function profileHeader(){
    let b=$('profileButton');
    if(b)b.textContent=model.user?.firstName?model.user.firstName+' · Profile':'Your profile'
}
function timeOffTable(query=''){
    let state=model.bambooTimeOff,entries=state?.entries||[],q=normalizedEmployeeName(query),shown=entries.filter(t=>normalizedEmployeeName(t.name+' '+t.employeeId).includes(q));
    return `<p>${state?.status==='success'?'Fetched '+esc(state.checkedAt)+' · '+esc(state.start)+' to '+esc(state.end):state?.status==='error'?'BambooHR time-off data unavailable; review schedule. '+esc(state.error):'No successful BambooHR time-off check has been made.'}</p><p>${shown.length} of ${entries.length} employee time-off records. Employees are matched by BambooHR ID when available; names are used only when an ID is absent. Company holidays are excluded.</p><div class="tablewrap"><table><thead><tr><th>Employee</th><th>BambooHR employee ID</th><th>Start</th><th>End</th><th>Roster match / location × role</th></tr></thead><tbody>${shown.map(t=>{
        let matches=model.roster.filter(e=>t.employeeId?String(e.bamboohrId)===String(t.employeeId):normalizedEmployeeName(e.name)===normalizedEmployeeName(t.name));return `<tr><td>${esc(t.name)}</td><td>${esc(t.employeeId)}</td><td>${t.start}</td><td>${t.end}</td><td>${matches.length?matches.map(e=>esc(e.location+' · '+e.role+' · '+e.id)).join('<br>')+(matches.length>1?'<small>Multiple BambooHR ID matches · all matching employees excluded</small>':''):'No roster match'}</td></tr>`
    }
    ).join('')}</tbody></table></div>`
}
function openTimeOffs(){
    $('timeOffDialog').innerHTML='<div class="dialoghead"><div><div class="eyebrow">BAMBOOHR</div><h2>Employee time-offs</h2></div><button type="button" data-bamboo-action="closeTimeOffs" aria-label="Close time-offs">✕</button></div><label>Find employee<input id="timeOffSearch" placeholder="Name or BambooHR employee ID"></label><div id="timeOffTable">'+timeOffTable()+'</div><div class="actions"><button type="button" data-action="refreshTimeOffs">Fetch current schedule period</button><button type="button" data-bamboo-action="closeTimeOffs">Close</button></div>';
    $('timeOffSearch').oninput=e=>$('timeOffTable').innerHTML=timeOffTable(e.target.value);
    $('timeOffDialog').showModal()
}
async function refreshTimeOffFromServer(){
    if(busy)return;
    busy=true;
    try{
    let {
        start,end
    }=schedulingTimeOffPeriod();
    let check=await prepareSchedulingTimeOff(start,end);
    if($('timeOffDialog')?.open){
        let query=$('timeOffSearch')?.value||'';
        $('timeOffTable').innerHTML=timeOffTable(query)
    }
    render(true);
    message(check.status==='success'?'BambooHR time-offs refreshed for '+start+' to '+end+'.':timeOffSummary(),check.status!=='success')
    }
    finally{
        busy=false
    }
}
function timeOffExportRows(runs){
    let a=[['Week commencing','Location','Role','Employee ID','Employee','Date','Status','Time-off check','Time-off source']];
    for(let r of runs)for(let e of r.employees)for(let d=0;d<7;d++)if(e.timeOff?.[d])a.push([r.start,r.location,r.role,e.id,e.name,addDays(r.start,d),'time-off',r.timeOffCheck?.status||'Not checked',r.timeOffCheck?'BambooHR':'No data']);
    return a
}
document.addEventListener('click',async e=>{
    let dismiss=e.target.closest('[data-dismiss-header]')?.dataset.dismissHeader;if(dismiss){
        dismissHeaderNotice(dismiss);return
    }
    let cmd=e.target.closest('[data-bamboo-action]')?.dataset.bambooAction;
    if(cmd==='downloadConnector'&&!busy){
        try{
            await downloadConnectorKit();$('profileStatus').textContent='Connector kit downloaded. Extract all files and run the launcher to open the app locally.'
        }
        catch(err){
            $('profileStatus').textContent='Download failed: '+err.message
        }
        return
    }
    if(cmd==='closeTimeOffs')$('timeOffDialog').close();

}
);
function initLocalConnector(){
    let loc=globalThis.location;
    if(!loc||!['127.0.0.1','localhost'].includes(loc.hostname)||loc.protocol!=='http:')return;
    try{
        let hash=new URLSearchParams(String(loc.hash||'').replace(/^#/,'')),token=hash.get('connector');
        if(token&&/^[A-Za-z0-9_-]{32,100}$/.test(token)){
            localConnectorToken=token;
            try{
                sessionStorage.setItem('cbl-bamboo-connector-token',token)
            }
            catch{

            }
            try{
                history.replaceState(null,'',loc.pathname+loc.search)
            }
            catch{

            }

        }
        else if(!localConnectorToken){
            let saved=sessionStorage.getItem('cbl-bamboo-connector-token');
            if(saved&&/^[A-Za-z0-9_-]{32,100}$/.test(saved))localConnectorToken=saved
        }

    }
    catch{

    }

}
function bambooTransport(){
    initLocalConnector();
    let loc=globalThis.location,local=loc&&['127.0.0.1','localhost'].includes(loc.hostname)&&loc.protocol==='http:';
    return local?{
        mode:localConnectorToken?'local':'localMissing',url:loc.origin+'/bamboo/time-offs'
    }
    :{
        mode:'direct',url:'https://cbljm.bamboohr.com/api/v1/time_off/whos_out'
    }

}
async function downloadConnectorKit(){
    let files={
        ...BAMBOO_CONNECTOR_FILES,
        ...await portableBundleFiles(),
    }
    ;
    if(files['Start-Windows.cmd'])files['Start-Windows.cmd']=files['Start-Windows.cmd'].replace(/\r?\n/g,'\r\n');
    downloadFile('CBL-Scheduling-Local-Connector.zip',new Blob([zipStore(files)],{
        type:'application/zip'
    }
    ))
}
let pendingTimeOffFallback=null,timeOffWorkbookImporting=false;
function schedulingTimeOffPeriod(){
    let start=model.controls.week;
    if(!validTimeOffDate(start))throw Error('Select a valid week commencing date in Controls first.');
    let weeks=scheduleWeeks(model);
    return {
        start,end:addDays(start,weeks*7-1)
    }

}
function parseTimeOffWorkbook(db){
    let match;
    for(let [sheet,rows] of Object.entries(db)){
        let rowIndex=rows.findIndex(r=>r.map(v=>String(v??'').trim().toLowerCase()).includes('employee')&&r.map(v=>String(v??'').trim().toLowerCase()).includes('attribute:type'));
        if(rowIndex>=0){
            match={
                sheet,rows,rowIndex
            }
            ;
            break
        }

    }
    if(!match)throw Error('Expected template headers: Employee, start, end, Attribute:type.');
    let {
        sheet,rows,rowIndex
    }
    =match,h=rows[rowIndex].map(v=>String(v??'').trim().toLowerCase()),nameCol=h.indexOf('employee'),startCol=h.indexOf('start'),endCol=h.indexOf('end'),typeCol=h.indexOf('attribute:type');
    if(startCol<0||endCol<0)throw Error('Both start and end columns are required.');
    let entries=[],holidays=0,duplicates=0,seen=new Set();
    for(let i=rowIndex+1;i<rows.length;i++){
        let row=rows[i]||[];
        if(row.every(v=>v===null||v===undefined||v===''))continue;
        let type=String(row[typeCol]??'').trim().toLowerCase().replace(/[\s_-]/g,'');
        if(type==='holiday'){
            holidays++;
            continue
        }
        if(type!=='timeoff')throw Error(sheet+' row '+(i+1)+': Attribute:type must be timeOff or holiday.');
        let dateValue=v=>{
            try{
                return isoDate(v)
            }
            catch{
                return ''
            }

        }
        ,name=String(row[nameCol]??'').trim(),start=dateValue(row[startCol]),end=dateValue(row[endCol]);
        if(!name||!validTimeOffDate(start)||!validTimeOffDate(end)||end<start)throw Error(sheet+' row '+(i+1)+': provide an Employee and valid start/end dates, with end on or after start.');
        let k=normalizedEmployeeName(name)+'|'+start+'|'+end;
        if(seen.has(k)){
            duplicates++;
            continue
        }
        seen.add(k);
        entries.push({
            id:'workbook-'+sheet+'-'+(i+1),type:'timeOff',employeeId:'',name,start,end
        }
        )
    }
    return {
        entries,holidays,duplicates,sheet
    }

}
function workbookCoversPeriod(file,start,end){
    return !!file&&Array.isArray(file.entries)&&validTimeOffDate(file.coverageStart)&&validTimeOffDate(file.coverageEnd)&&file.coverageStart<=start&&file.coverageEnd>=end
}
function applyTimeOffWorkbook(state){
    let file=model.timeOffWorkbook;
    if(!workbookCoversPeriod(file,state.start,state.end))throw Error('The saved workbook has not been confirmed for this schedule period.');
    let active={
        status:'success',source:'workbook',sourceName:file.name,start:state.start,end:state.end,entries:file.entries.filter(t=>t.end>=state.start&&t.start<=state.end),checkedAt:new Date().toISOString(),uploadedAt:file.uploadedAt,apiStatus:state.status,apiError:state.error||'',error:'',coverageStart:file.coverageStart,coverageEnd:file.coverageEnd
    }
    ;
    model.bambooTimeOff=active;
    return active
}
async function prepareSchedulingTimeOff(start,end){
    return prepareTimeOff(start,end)
}
function offerTimeOffFallback(state){
    return new Promise(resolve=>{
        pendingTimeOffFallback={
            state,resolve
        }
        ;openTimeOffWorkbook(state)
    }
    )
}
function openTimeOffWorkbook(state=null){
    let pending=!!pendingTimeOffFallback,p=state||schedulingTimeOffPeriod(),file=model.timeOffWorkbook;
    $('timeOffWorkbookDialog').innerHTML=`<div class="dialoghead"><div><div class="eyebrow">TIME-OFF WORKBOOK</div><h2>${pending?'BambooHR unavailable · choose a fallback':'Upload employee time-offs'}</h2></div><button type="button" data-timeoff-workbook="close" aria-label="${pending?'Continue without time-offs':'Close'}">✕</button></div>${state?.error?`<p class="badtext">${esc(state.error)}</p>`:''}<p>Schedule period: <b>${p.start} to ${p.end}</b>. Upload the Time-off template workbook with <b>Employee, start, end, Attribute:type</b> columns. Only employee timeOff entries are applied; holiday rows are ignored.</p>${file?`<p>Saved workbook: <b>${esc(file.name)}</b> · ${file.entries.length} employee time-off records · confirmed ${file.coverageStart} to ${file.coverageEnd}. Leave the file field empty to reuse it after confirming coverage below.</p>`:''}<label>Time-off workbook · XLSX<input type="file" id="timeOffWorkbookFile" accept=".xlsx"></label><div class="formgrid"><label>Workbook coverage starts<input type="date" id="timeOffCoverageStart" value="${p.start}"></label><label>Workbook coverage ends<input type="date" id="timeOffCoverageEnd" value="${p.end}"></label></div><label class="check"><input type="checkbox" id="timeOffCoverageConfirmed"> I confirm this workbook contains the approved employee time-offs for the coverage period above.</label><p class="note">Coverage must include the entire schedule period. A date without a matching workbook entry will be treated as no recorded time-off. A successfully confirmed workbook is saved with the workspace and reused within that coverage period whenever BambooHR is unavailable or API credentials are not configured. A successful API response takes precedence.</p><p id="timeOffWorkbookStatus" role="status"></p><div class="actions"><button type="button" class="primary" data-timeoff-workbook="apply">${pending?'Apply workbook & continue scheduling':'Save time-off workbook'}</button><button type="button" data-timeoff-workbook="close">${pending?'Continue without time-offs':'Cancel'}</button></div>`;
    $('timeOffWorkbookDialog').oncancel=e=>{
        e.preventDefault();
        if(!timeOffWorkbookImporting)closeTimeOffWorkbook()
    }
    ;
    $('timeOffWorkbookDialog').showModal()
}
function closeTimeOffWorkbook(){
    if(timeOffWorkbookImporting)return;
    $('timeOffWorkbookDialog').close();
    if(pendingTimeOffFallback){
        let {
            state,resolve
        }
        =pendingTimeOffFallback;
        pendingTimeOffFallback=null;
        resolve(state)
    }

}
async function importTimeOffWorkbook(){
    if(timeOffWorkbookImporting)return;
    let pending=pendingTimeOffFallback,period=pending?.state||schedulingTimeOffPeriod(),start=$('timeOffCoverageStart').value,end=$('timeOffCoverageEnd').value;
    if(!$('timeOffCoverageConfirmed').checked)throw Error('Confirm that the workbook includes approved time-offs for the coverage period.');
    if(!validTimeOffDate(start)||!validTimeOffDate(end)||end<start||start>period.start||end<period.end)throw Error('Confirmed workbook coverage must include '+period.start+' to '+period.end+'.');
    let file=$('timeOffWorkbookFile').files[0],previous=model.timeOffWorkbook;
    if(!file&&!previous)throw Error('Select the time-off workbook to upload.');
    timeOffWorkbookImporting=true;
    let ownedBusy=!busy;
    if(ownedBusy)busy=true;
    try{
        $('timeOffWorkbookStatus').textContent='Reading and validating employee time-offs…';
        let parsed;
        if(file){
            if(file.size>60e6)throw Error('Workbook exceeds 60 MB.');
            parsed=parseTimeOffWorkbook(await parseXlsx(await file.arrayBuffer()))
        }
        else parsed={
            entries:previous.entries,holidays:previous.holidays||0,duplicates:previous.duplicates||0,sheet:previous.sheet
        }
        ;
        let next={
            ...parsed,name:file?.name||previous.name,uploadedAt:file?new Date().toISOString():previous.uploadedAt,coverageStart:start,coverageEnd:end
        }
        ;
        let oldActive=model.bambooTimeOff;
        model.timeOffWorkbook=next;
        let state=applyTimeOffWorkbook(pending?.state||{
            status:model.bambooTimeOff?.status==='error'?'error':'notConfigured',error:model.bambooTimeOff?.error||'',start:period.start,end:period.end
        }
        );
        try{
            await saveState()
        }
        catch(e){
            model.timeOffWorkbook=previous;
            model.bambooTimeOff=oldActive;
            throw e
        }
        $('timeOffWorkbookDialog').close();
        if(pending){
            pendingTimeOffFallback=null;
            pending.resolve(state)
        }
        else{
            render();
            if($('timeOffTable'))$('timeOffTable').innerHTML=timeOffTable($('timeOffSearch')?.value||'');
            message(parsed.entries.length+' employee time-off records saved from '+next.name+'; '+parsed.holidays+' holiday rows ignored. Generate schedules or Refresh & shuffle all to apply them.'+(storageMode==='session'?' Session only: save a workspace backup or portable ZIP bundle.':''))
        }

    }
    finally{
        timeOffWorkbookImporting=false;
        if(ownedBusy)busy=false
    }

}
document.addEventListener('click',async e=>{
    let cmd=e.target.closest('[data-timeoff-workbook]')?.dataset.timeoffWorkbook;if(!cmd||timeOffWorkbookImporting)return;if(cmd==='close'){
        closeTimeOffWorkbook();return
    }
    if(cmd==='apply'){
        try{
            await importTimeOffWorkbook()
        }
        catch(err){
            $('timeOffWorkbookStatus').textContent='Workbook not applied: '+err.message
        }

    }

}
);
let storageMode='unknown',storageReason='';
let expandedPanels=new Set(),attendanceSort={shifts:{key:'',direction:'asc'},scores:{key:'',direction:'asc'}},model=null,page='home',filterLoc='All',filterRole='All',employeeLocationFilter='All',employeeRoleFilter='All',attendanceLocationFilter='All',attendanceRoleFilter='All',attendancePeriodMode='day',attendanceSelectedDate='',attendanceStartMonth='',attendanceEndMonth='',search='',resultFilter='All',previewId='',busy=false,sourceBytes=null,tenantAuthCsrfToken='',tenantMembership=null;
let employeeDirectory=[],scheduleLocations=[],directoryError='',employeeSyncStatus='',pendingEmployeeSyncConflicts=[],pendingSourceImport=null,sourceReviewRows=[],assignLocationId='',assignEmployeeIds=new Set(),assignCandidateIds=new Set(),selectedEmployeeIds=new Set(),publishSelection=[],publishConfigured=false,publishError='',publishPreview=null,publishResults=[],attendanceData=null,attendanceSyncStatus='',attendanceLastAttempt=0,attendanceSyncTimer=null,attendanceLoadSequence=0,sharedRoster=null,sharedRosterError='',sharedMeta=null,sharedMetaError='';
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}
[c])),f=(v,d=0)=>Number(v||0).toLocaleString('en-US',{
    maximumFractionDigits:d
}
),sum=a=>a.reduce((s,x)=>s+x,0),percent=v=>v===null?'':Math.round(v*1000000)/10000;
function membershipFeatureEnabled(feature){
    return tenantMembership?.features?.[feature]===true
}
function message(text,error=false){
    dismissedHeaderNotices.delete('notice');
    if($('noticeWrap'))$('noticeWrap').hidden=!text;
    $('notice').textContent=text;
    $('notice').className=error?'notice error':'notice';

}
async function directoryRequest(path,options={}){
    let response=await fetch('/api'+path,{
        ...options,headers:{
            'Content-Type':'application/json',...(options.headers||{})
        }
    }),body=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(body.error||'Request to '+path+' failed with HTTP '+response.status+'.');
    return body
}
function applySharedRosterSettings(result){
    sharedRoster=result;sharedRosterError='';
    if(!result.configured||!model)return;
    model.locked=result.locked;
    for(const remotePool of result.pools){
        const pool=model.pools.find(item=>item.location===remotePool.location&&item.role===remotePool.role);
        if(!pool)continue;
        const shares=new Map(poolStarts(pool).map((start,index)=>[Number(start),pool.shares[index]]));
        pool.shiftStarts=remotePool.starts.map(Number);
        pool.shares=pool.shiftStarts.map(start=>shares.has(start)?shares.get(start):null);
    }
    for(const remote of result.employees){
        if(!remote.settings)continue;
        const employee=model.roster.find(item=>String(item.id)===String(remote.employeeId));
        if(!employee)continue;
        Object.assign(employee,remote.settings);
        employee.shiftAvailability={...remote.settings.shiftAvailability};
        employee.allow=STARTS.map(start=>employee.shiftAvailability[String(start)]??null);
    }
}
async function loadSharedRosterSettings(){
    try{
        applySharedRosterSettings(await directoryRequest('/roster-settings'))
    }
    catch(error){
        sharedRoster=null;
        sharedRosterError=error.message
    }
}
function applySharedMetaSettings(result){
    sharedMeta=result;sharedMetaError='';
    if(!result.configured||!model)return;
    if(!model.locations.length&&result.locations.length)model.locations=result.locations.map(location=>clone(location));
    if(!sharedRoster?.configured)model.locked=result.locked;
    for(const remote of result.locations){
        const location=model.locations.find(item=>item.name.toLowerCase()===remote.name.toLowerCase());
        if(!location)continue;
        location.intensity=remote.intensity.slice();
        location.open=remote.open.slice();
    }
}
async function loadSharedMetaSettings(){
    if(!tenantAuthPrimaryAdmin){
        sharedMeta=null;sharedMetaError='';
        return
    }
    try{
        applySharedMetaSettings(await directoryRequest('/meta-settings'))
    }
    catch(error){
        sharedMeta=null;
        sharedMetaError=error.message
    }
}
function sharedRosterImportPayload(){
    if(!model||!tenantAuthTenantId)throw Error('The workspace or business identity is not ready.');
    const employees=employeeDirectory.map(employee=>{
        const profile=model.roster.find(item=>String(item.id)===String(employee.id));
        if(!profile)throw Error('The local workspace is missing '+employee.name+'’s roster profile. Reload the roster and retry.');
        const starts=poolStarts(model.pools.find(pool=>pool.location===profile.location&&pool.role===profile.role));
        return {
            employeeId:String(employee.id),
            settings:{
                flex:profile.flex??'',reason:profile.reason??'',preferred:profile.preferred??null,
                proximity:profile.proximity??null,random:profile.random??null,attendance:profile.attendance??null,
                days:Array.isArray(profile.days)?profile.days.slice(0,7):Array(7).fill(null),
                shiftAvailability:Object.fromEntries(starts.map(start=>[String(start),employeeStartPermission(profile,start)??null]))
            }
        }
    });
    return {
        tenantId:tenantAuthTenantId,locked:!!model.locked,
        pools:model.pools.map(pool=>({location:pool.location,role:pool.role,starts:poolStarts(pool).map(Number)})),
        employees
    }
}
function sharedRosterEmployeePayload(employee){
    const profile=model.roster.find(item=>String(item.id)===String(employee.id));
    if(!profile)throw Error('The local workspace is missing '+employee.name+'’s roster profile. Reload the roster and retry.');
    const starts=poolStarts(model.pools.find(pool=>pool.location===employee.location&&pool.role===employee.role));
    return {
        employeeId:String(employee.id),
        settings:{
            flex:profile.flex??'',reason:profile.reason??'',preferred:profile.preferred??null,
            proximity:profile.proximity??null,random:profile.random??null,attendance:profile.attendance??null,
            days:Array.isArray(profile.days)?profile.days.slice(0,7):Array(7).fill(null),
            shiftAvailability:Object.fromEntries(starts.map(start=>[String(start),employeeStartPermission(profile,start)??null]))
        }
    }
}
async function initializeSharedRoster(){
    if(!tenantAuthPrimaryAdmin)throw Error('Only the primary administrator can initialize the shared roster.');
    const payload=sharedRosterImportPayload(),headers={'X-CSRF-Token':tenantAuthCsrfToken};
    const preview=await directoryRequest('/roster-settings/import/preview',{
        method:'POST',headers,body:JSON.stringify(payload)
    });
    const warningText=preview.warnings.length?'\n\nReview warnings:\n• '+preview.warnings.join('\n• '):'';
    const summary=`Import ${preview.employeeCount} employee profiles and ${preview.poolCount} location-role pools to the business server? This is one-time setup and will not overwrite existing server data.${warningText}`;
    if(!confirm(summary))return;
    await directoryRequest('/roster-settings/import',{
        method:'POST',headers,body:JSON.stringify({...payload,confirmed:true})
    });
    await loadSharedRosterSettings();
    await saveState();
    render(true);
    message('Shared roster initialized from the reviewed browser workspace.')
}
async function syncMissingSharedRosterEmployees(){
    if(!sharedRoster?.configured)throw Error('Initialize the shared roster first.');
    const existing=new Set(sharedRoster.employees.filter(employee=>employee.settings).map(employee=>String(employee.employeeId)));
    const missing=employeeDirectory.filter(employee=>!existing.has(String(employee.id))&&employee.location&&employee.role&&model.pools.some(pool=>pool.location===employee.location&&pool.role===employee.role));
    if(!missing.length)throw Error('There are no new employees to synchronize.');
    const employees=missing.map(sharedRosterEmployeePayload);
    if(!confirm(`Add ${employees.length} new employee profile(s) to the shared roster? Existing employee settings will not be overwritten.`))return;
    const result=await directoryRequest('/roster-settings/employees',{
        method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
        body:JSON.stringify({revision:sharedRoster.revision,confirmed:true,employees})
    });
    await loadSharedRosterSettings();
    await saveState();
    render(true);
    message(`${result.added} new employee profile(s) added to the shared roster.`)
}
async function syncSharedRosterPools(){
    if(!sharedRoster?.configured)throw Error('Initialize the shared roster first.');
    const pools=model.pools.map(pool=>({location:pool.location,role:pool.role,starts:poolStarts(pool).map(Number)}));
    if(!confirm(`Update shared possible shift starts to match ${pools.length} location-role pool(s)? Employee settings will be preserved; preferred starts currently in use cannot be removed.`))return;
    await saveSharedRosterConfiguration(model.locked,pools);
    await loadSharedRosterSettings();
    render(true);
    message('Shared possible shift starts synchronized.')
}
async function saveSharedRosterConfiguration(locked,pools){
    if(!sharedRoster?.configured)return;
    const result=await directoryRequest('/roster-settings/configuration',{
        method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
        body:JSON.stringify({revision:sharedRoster.revision,locked,pools})
    });
    sharedRoster={...sharedRoster,revision:result.revision,locked:result.locked,pools:result.pools};
}
function sharedMetaImportPayload(){
    if(!model||!tenantAuthTenantId)throw Error('The workspace or business identity is not ready.');
    return {
        tenantId:tenantAuthTenantId,locked:!!model.locked,
        locations:model.locations.map(location=>({
            name:location.name,intensity:location.intensity.slice(),open:location.open.slice()
        }))
    }
}
async function initializeSharedMeta(){
    if(!tenantAuthPrimaryAdmin)throw Error('Only the primary administrator can initialize shared META settings.');
    const payload=sharedMetaImportPayload(),headers={'X-CSRF-Token':tenantAuthCsrfToken};
    const preview=await directoryRequest('/meta-settings/import/preview',{
        method:'POST',headers,body:JSON.stringify(payload)
    });
    if(!confirm(`Import operating days and intensity for ${preview.locationCount} physical location(s) to the business server? This is one-time setup and will not overwrite existing server data.`))return;
    await directoryRequest('/meta-settings/import',{
        method:'POST',headers,body:JSON.stringify({...payload,confirmed:true})
    });
    await loadSharedMetaSettings();
    await saveState();
    render(true);
    message('Shared META settings initialized from the reviewed browser workspace.')
}
async function syncSharedMetaLocations(){
    if(!sharedMeta?.configured)throw Error('Initialize shared META settings first.');
    if(sharedMeta.locked)throw Error('Unlock settings in Controls before synchronizing META locations.');
    const known=new Set(sharedMeta.locations.map(location=>location.name.toLowerCase()));
    const additions=model.locations.filter(location=>!known.has(location.name.toLowerCase()));
    if(!additions.length)throw Error('There are no new META locations to synchronize.');
    const locations=[...sharedMeta.locations,...additions.map(location=>({
        name:location.name,intensity:location.intensity.slice(),open:location.open.slice()
    }))];
    if(!confirm(`Add ${additions.length} new physical location(s) to shared META settings? Existing server settings will be preserved.`))return;
    await saveSharedMetaConfiguration(sharedMeta.locked,locations);
    applySharedMetaSettings(sharedMeta);
    await saveState();
    render(true);
    message('New META locations synchronized without changing existing settings.')
}
async function saveSharedMetaConfiguration(locked,locations){
    if(!sharedMeta?.configured)return;
    const result=await directoryRequest('/meta-settings/configuration',{
        method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
        body:JSON.stringify({revision:sharedMeta.revision,locked,locations})
    });
    sharedMeta={...sharedMeta,revision:result.revision,locked:result.locked,locations:result.locations};
}
async function acceptLocationsOnServer(source,locations){
    if(!tenantAuthPrimaryAdmin)throw Error('Only the primary administrator can accept locations.');
    sharedMeta=await directoryRequest('/meta-settings');
    sharedMetaError='';
    const payload={source,locations};
    if(sharedMeta?.configured)payload.revision=sharedMeta.revision;
    return directoryRequest('/meta-settings/locations/accept',{
        method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify(payload)
    })
}
function applyAcceptedLocations(result,target=model,replace=false){
    if(replace)target.locations=result.locations.map(location=>clone(location));
    else for(const name of result.accepted){
        if(target.locations.some(location=>location.name.toLowerCase()===name.toLowerCase()))continue;
        const accepted=result.locations.find(location=>location.name.toLowerCase()===name.toLowerCase());
        if(accepted)target.locations.push(clone(accepted))
    }
    sharedMeta={configured:true,revision:result.revision,locked:result.locked,locations:result.locations};
    sharedMetaError=''
}
async function syncSharedRosterEmployeeField(employee,field,value){
    if(!sharedRoster?.configured)return;
    const record=sharedRoster.employees.find(item=>String(item.employeeId)===String(employee.id));
    if(!record||!record.settings||!Number.isInteger(record.revision)){
        throw Error('This employee has no shared profile yet. Synchronize new employees first.')
    }
    const next=field==='flex'||field==='reason'?value:value===''?null:Number(value);
    const result=await directoryRequest('/roster-settings/'+encodeURIComponent(employee.id),{
        method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
        body:JSON.stringify({revision:record.revision,changes:{[field]:next}})
    });
    record.settings=result.settings;record.revision=result.revision;
    await saveState()
}
let accessAccounts=[],accessAccountsError='',accessTemporaryPassword=null,attendanceNotificationTimer=null,portalVisibilityWeeks=4;
async function loadAccessAccounts(){
    try{
        let [accounts,portal]=await Promise.all([
            directoryRequest('/access-accounts'),directoryRequest('/schedule-portal/settings')
        ]);
        accessAccounts=accounts.accounts;
        portalVisibilityWeeks=portal.visibilityWeeks;
        accessAccountsError=''
    }
    catch(error){
        accessAccountsError=error.message
    }
    if(page==='settings')render(true)
}
function portalSettingsPanel(){
    let managers=accessAccounts.filter(account=>account.role==='manager');
    return panel('Schedule portal',`<label>Schedule visibility · weeks including the current week<input id="portalVisibilityWeeks" type="number" min="1" max="52" value="${portalVisibilityWeeks}"></label><div class="actions"><button type="button" data-action="savePortalSettings">Save portal settings</button><a class="button" href="/access">Open manager / employee portal</a></div><p class="note">Accepted schedules only. Employees need their individual login, a scheduled assignment and the six-digit location/role/period code. Codes expire at the end of the period in Jamaica time and are included in manager confirmation drafts. Managers see all their assigned locations without a code.</p><h3>Manager personal employee link</h3><label>Manager<select id="managerLinkAccount">${managers.map(account=>`<option value="${esc(account.id)}">${esc(account.displayName)} · linked employee: ${esc(account.employeeId||'none')}</option>`).join('')}</select></label><label>Employee<select id="managerLinkEmployee"><option value="">Unlink</option>${employeeDirectory.filter(employee=>employee.active).map(employee=>`<option value="${esc(employee.id)}">${esc(employee.name)} (${esc(employee.id)})</option>`).join('')}</select></label><button type="button" data-action="linkManagerEmployee" ${managers.length?'':'disabled'}>Save manager employee link</button><p class="note">Link changes revoke existing manager sessions. Existing accounts are not merged; conflicts must be resolved explicitly.</p>`)
}
function accessAccountsPanel(){
    let employeeOptions=(employeeDirectory||[]).filter(employee=>employee.active).map(employee=>`<option value="${esc(employee.id)}">${esc(employee.name)} (${esc(employee.id)})</option>`).join('');
    let rows=accessAccounts.map(account=>`<tr><td>${esc(account.displayName)}</td><td>${esc(account.role)}</td><td>${esc(account.email||account.employeeId||'')}</td><td>${account.active?'Active':'Disabled'}${account.mustChangePassword?' · temporary password':''}${account.role==='manager'?(account.mfaEnabled?' · MFA on':' · MFA pending'):''}${account.role==='manager'&&!account.scopeEmployees?' · no matching schedule location':''}</td><td><div class="actions employee-actions"><button type="button" data-action="changeAccessRole" data-id="${esc(account.id)}">Change role</button><button type="button" data-action="resetAccessPassword" data-id="${esc(account.id)}">Reset password</button>${account.role==='manager'?`<button type="button" data-action="resetAccessPassword" data-reset-mfa="true" data-id="${esc(account.id)}">Reset password &amp; MFA</button>`:''}<button type="button" data-action="toggleAccessAccount" data-id="${esc(account.id)}" data-active="${account.active?'false':'true'}">${account.active?'Disable':'Enable'}</button></div></td></tr>`).join('');
    return panel('Manager &amp; employee access',`${accessAccountsError?`<p class="badtext">${esc(accessAccountsError)}</p>`:''}${accessTemporaryPassword?`<div class="callout" role="status"><b>Temporary password for ${esc(accessTemporaryPassword.name)}:</b> <code>${esc(accessTemporaryPassword.password)}</code><br>Share it securely. It is shown once and expires in ${accessTemporaryPassword.hours} hours. The user must replace it at first sign-in at <code>/access</code>.</div>`:''}<div class="grid"><label>Role<select id="accessRole"><option value="manager">Manager (MFA required)</option><option value="employee">Employee (Silver and above)</option></select></label><label>Name<input id="accessName" maxlength="120"></label><label>Email (required for managers)<input id="accessEmail" type="email" maxlength="254"></label><label>Employee (employee accounts)<select id="accessEmployee"><option value="">—</option>${employeeOptions}</select></label></div><div class="actions"><button type="button" class="primary" data-action="createAccessAccount">Create account</button><button type="button" data-action="reloadAccessAccounts">Refresh</button></div><div class="tablewrap"><table><thead><tr><th>Name</th><th>Role</th><th>Sign-in</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows||'<tr><td colspan="5">No manager or employee accounts yet.</td></tr>'}</tbody></table></div>`,'Managers see attendance only for employees at schedule locations whose manager email matches their email. Employees see only their own attendance.')+portalSettingsPanel()
}
function openAccessRoleDialog(id){
    const account=accessAccounts.find(item=>item.id===id);
    if(!account)throw Error('Account not found. Refresh and retry.');
    let dialog=$('accessRoleDialog');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='accessRoleDialog';dialog.className='wide-dialog';document.body.append(dialog);}
    dialog.dataset.accountId=id;dialog.dataset.previousRole=account.role;
    dialog.innerHTML=`<div class="dialoghead"><h2>Change role: ${esc(account.displayName)}</h2><button type="button" data-dialog-close="accessRoleDialog" aria-label="Close">Close</button></div><form id="accessRoleForm"><label>New role<select id="accessNewRole"><option value="manager" ${account.role==='employee'?'selected':''}>Manager (MFA required)</option><option value="employee" ${account.role==='manager'?'selected':''}>Employee</option></select></label><label>Email (required for managers)<input id="accessRoleEmail" type="email" maxlength="254" value="${esc(account.email||'')}"></label><label>Employee (required for employees; optional personal link for managers)<select id="accessRoleEmployee"><option value="">No personal employee link</option>${employeeDirectory.filter(employee=>employee.active).map(employee=>`<option value="${esc(employee.id)}" ${employee.id===account.employeeId?'selected':''}>${esc(employee.name)} (${esc(employee.id)})</option>`).join('')}</select></label><p class="note">The account, password, enabled/disabled state and history are retained. Existing sessions will be revoked. Managers must use MFA and only manage schedule locations matching their email. Employee access and manager personal links require an eligible membership.</p><p id="accessRoleError" class="badtext" role="alert"></p><div class="actions"><button type="submit" class="primary">Save role change</button><button type="button" data-dialog-close="accessRoleDialog">Cancel</button></div></form>`;
    const sync=()=>{$('accessRoleEmail').required=$('accessNewRole').value==='manager';$('accessRoleEmployee').required=$('accessNewRole').value==='employee';};
    $('accessNewRole').onchange=sync;sync();
    dialog.onkeydown=event=>{if(event.key==='Escape'){event.preventDefault();dialog.close();}};
    $('accessRoleForm').onsubmit=async event=>{
        event.preventDefault();
        if(!confirm('Change this account role and revoke existing sessions?'))return;
        const submit=event.currentTarget.querySelector('[type=submit]');submit.disabled=true;$('accessRoleError').textContent='';
        try{
            await directoryRequest('/access-accounts/'+encodeURIComponent(id)+'/role',{
                method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({role:$('accessNewRole').value,previousRole:dialog.dataset.previousRole,authVersion:account.authVersion,email:$('accessRoleEmail').value.trim(),employeeId:$('accessRoleEmployee').value||null})
            });
            dialog.close();accessTemporaryPassword=null;
            await loadAccessAccounts();
            message('Account role changed. The user must sign in again; managers require MFA.');
        }catch(error){$('accessRoleError').textContent=error.message;}
        finally{submit.disabled=false;}
    };
    dialog.showModal()
}
let attendanceNotifications=[],archivedNotifications=[],pendingTradeNotifications=[],notificationView='active',expandedNotifications=new Set();
function renderNotificationBadge(){
    let badge=$('notificationBadge'),unread=attendanceNotifications.filter(item=>!item.read).length+pendingTradeNotifications.filter(item=>item.unread).length;
    if(!badge)return;
    badge.textContent=unread;
    badge.hidden=unread===0
}
function notificationDetailHtml(item){
    let label={absent:'Absent',early_leave:'Left early'}[item.kind]||'Late';
    return `<dl class="notification-detail"><dt>Status</dt><dd>${esc(label)}</dd><dt>Employee</dt><dd>${esc(item.employeeName||item.employeeId)} (${esc(item.employeeId)})</dd><dt>Location</dt><dd>${esc(item.location||'Not recorded')}</dd><dt>Shift date</dt><dd>${esc(item.date)}</dd><dt>Shift time</dt><dd>${item.shiftStart==null?'Not recorded':esc(timeLabel(Number(item.shiftStart)))+' start'}</dd><dt>Detected</dt><dd>${esc(item.createdAt)}</dd></dl>`
}
function renderNotificationPanel(){
    let box=$('notificationPanel');
    if(!box)return;
    let archive=notificationView==='archive',items=archive?archivedNotifications:attendanceNotifications;
    let list=items.map(item=>{
        let open=expandedNotifications.has(item.id);
        return `<li class="notification-item ${item.read||archive?'':'unread'}"><div class="notification-row"><button type="button" class="notification-summary" data-action="openNotification" data-id="${esc(item.id)}" aria-expanded="${open}">${esc(item.date)}: ${esc(item.message)}</button>${archive?'':`<button type="button" class="notification-remove" data-action="archiveNotification" data-id="${esc(item.id)}" aria-label="Remove notification" title="Remove (moves to archives)">✕</button>`}</div>${open?notificationDetailHtml(item):''}</li>`
    }).join('')||`<li class="notification-item"><span class="notification-summary">${archive?'No archived notifications.':'No notifications.'}</span></li>`;
    const trades=archive?'':pendingTradeNotifications.map(trade=>`<li class="notification-item ${trade.unread?'unread':''}"><button type="button" class="notification-summary" data-action="openTradeApproval" data-id="${esc(trade.id)}">Shift trade pending administrator approval · week ${esc(trade.start||'unavailable')} · ${esc(trade.employeeNameA)} ↔ ${esc(trade.employeeNameB)}</button></li>`).join('');
    box.innerHTML=`<div class="notification-head"><b>${archive?'Archived notifications':'Notifications'}</b><div class="actions">${archive?'':'<button type="button" data-action="readNotifications">Mark all read</button>'}<button type="button" data-action="toggleNotifications" aria-label="Close notifications">Close</button></div></div>${trades?`<h3>Shift trade approvals</h3><ul>${trades}</ul>`:''}<h3>Attendance</h3><ul>${list}</ul><div class="notification-foot"><button type="button" data-action="${archive?'showActiveNotifications':'showNotificationArchive'}">${archive?'← Back to notifications':'View archives'}</button></div>`
}
async function showNotificationArchive(){
    let result=await directoryRequest('/attendance/notifications?archived=1');
    archivedNotifications=result.notifications;
    notificationView='archive';
    renderNotificationPanel()
}
function showActiveNotifications(){
    notificationView='active';
    renderNotificationPanel()
}
async function archiveNotification(id){
    await directoryRequest('/attendance/notifications/archive',{
        method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify({ids:[id]})
    });
    expandedNotifications.delete(id);
    await pollAttendanceNotifications()
}
async function pollAttendanceNotifications(){
    if(!$('notificationBadge'))return;
    try{
        let [result,trades]=await Promise.all([
            directoryRequest('/attendance/notifications'),
            membershipFeatureEnabled('shiftTrades')?directoryRequest('/shift-trades'):Promise.resolve({trades:[]})
        ]);
        attendanceNotifications=result.notifications;
        pendingTradeNotifications=trades.trades.filter(trade=>trade.state==='manager_accepted'&&trade.actions.includes('approve'));
        renderNotificationBadge();
        renderNotificationPanel()
    }
    catch(error){message('Unable to refresh notifications: '+error.message,true);}
}
async function openTradeApproval(id){
    const trade=pendingTradeNotifications.find(item=>item.id===id);
    if(!trade)throw Error('This trade is no longer pending. Refresh notifications.');
    let dialog=$('tradeApprovalDialog');
    if(!dialog){
        dialog=document.createElement('dialog');dialog.id='tradeApprovalDialog';dialog.className='wide-dialog trade-approval-dialog';
        dialog.innerHTML='<div class="dialoghead"><h2>Shift trade approval</h2><button type="button" data-dialog-close="tradeApprovalDialog">Close</button></div><iframe title="Administrator shift trade inbox"></iframe>';
        dialog.onkeydown=event=>{if(event.key==='Escape'){event.preventDefault();dialog.close();}};
        dialog.onclose=()=>{dialog.querySelector('iframe').src='about:blank';pollAttendanceNotifications();};
        document.body.append(dialog);
    }
    $('notificationPanel')?.remove();
    dialog.querySelector('iframe').src='/trades?adminView=1&trade='+encodeURIComponent(id)+'&theme='+encodeURIComponent(document.documentElement.dataset.theme||'light');
    if(!dialog.open)dialog.showModal();
    if(trade.unread){
        await directoryRequest('/shift-trades/'+encodeURIComponent(id)+'/read',{
            method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify({version:trade.version})
        });
        await pollAttendanceNotifications();
    }
}
async function openNotification(id){
    let item=attendanceNotifications.find(entry=>entry.id===id)||archivedNotifications.find(entry=>entry.id===id);
    if(!item)return;
    if(expandedNotifications.has(id))expandedNotifications.delete(id);
    else expandedNotifications.add(id);
    if(!item.read&&!item.archived){
        item.read=true;
        try{
            await directoryRequest('/attendance/notifications/read',{
                method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify({ids:[id]})
            })
        }
        catch{
            item.read=false
        }
    }
    renderNotificationBadge();
    renderNotificationPanel()
}
function toggleNotificationPanel(){
    let existing=$('notificationPanel');
    if(existing){
        existing.remove();
        return
    }
    let box=document.createElement('div'),bell=$('notificationButton').getBoundingClientRect();
    notificationView='active';
    box.id='notificationPanel';
    box.className='notification-panel';
    box.setAttribute('role','dialog');
    box.setAttribute('aria-label','Notifications');
    box.style.top=Math.round(bell.bottom+6)+'px';
    box.style.right=Math.max(8,Math.round(window.innerWidth-bell.right))+'px';
    document.body.append(box);
    renderNotificationPanel()
}
function startNotificationPolling(){
    if(attendanceNotificationTimer)clearInterval(attendanceNotificationTimer);
    attendanceNotificationTimer=setInterval(()=>{
        if(!document.hidden)pollAttendanceNotifications()
    },30000);
    pollAttendanceNotifications()
}
function blankRosterProfile(employee,index){
    let pool=model.pools.find(item=>item.location===employee.location&&item.role===employee.role),starts=poolStarts(pool);
    return {
        id:employee.id,name:employee.name,flex:'',reason:'',preferred:null,proximity:null,random:null,attendance:null,
        allow:Array(4).fill(0),days:Array(7).fill(null),previous:-1,location:employee.location,role:employee.role,index,
        shiftAvailability:Object.fromEntries(starts.map(start=>[String(start),0])),
        bamboohrId:employee.bamboohrId,scheduleLocationId:employee.scheduleLocationId,active:employee.active,sourceType:employee.source
    }
}
function roleFitsScheduleGroup(role,scheduleLocation){
    let value=String(role||'').trim().toLowerCase(),group=String(scheduleLocation?.roleGroup||'').trim().toLowerCase();
    if(!group)return true;
    if(group==='warehouse/delivery')return value==='warehouse'||value==='dc associate';
    if(group.includes('supervisor'))return value.includes('supervisor');
    if(group.includes('settlement'))return value.includes('settlement');
    return value===group
}
async function loadDirectoryData(){
    try{
        let [employeeResult,locationResult]=await Promise.all([
            directoryRequest('/employees'),directoryRequest('/schedule-locations')
        ]);
        employeeDirectory=employeeResult.employees;
        scheduleLocations=locationResult.scheduleLocations;
        let rosterById=new Map(model.roster.map(employee=>[String(employee.id),employee]));
        let rosterByBambooId=new Map(model.roster.filter(employee=>employee.bamboohrId).map(employee=>[String(employee.bamboohrId),employee]));
        for(let employee of employeeDirectory){
            let existing=rosterById.get(employee.id)||(employee.source==='bamboohr'?rosterByBambooId.get(String(employee.bamboohrId)):null);
            if(existing){
                existing.id=employee.id;
                existing.name=employee.name;
                existing.location=employee.location;
                existing.role=employee.role;
                existing.bamboohrId=employee.bamboohrId;
                existing.scheduleLocationId=employee.scheduleLocationId;
                existing.active=employee.active
                existing.sourceType=employee.source;
                rosterById.set(employee.id,existing)
            }
            else{
                model.roster.push(blankRosterProfile(employee,model.roster.length))
            }
        }
        for(let employee of model.roster){
            if(!employeeDirectory.some(record=>record.id===String(employee.id)||(employee.bamboohrId&&record.bamboohrId===employee.bamboohrId)))employee.active=false
        }
        model.roster.forEach((employee,index)=>employee.index=index);
        migrateScheduleWeeks(model);
        await loadSharedRosterSettings();
        await loadSharedMetaSettings();
        directoryError=''
    }
    catch(error){
        directoryError=error.message
    }
}
function applyAttendanceScores(data){
    if(!Array.isArray(data?.scores))return false;
    let scores=new Map(data.scores.map(item=>[String(item.employeeId),item.score===null?null:Number(item.score)])),changed=false;
    for(let employee of model.roster){
        let id=String(employee.id);
        if(!scores.has(id))continue;
        let score=scores.get(id);
        if(employee.attendance!==score){
            employee.attendance=score;
            changed=true
        }
    }
    return changed
}
function attendancePeriodRange(){
    if(attendancePeriodMode==='day'){
        let selectedDate=attendanceSelectedDate||attendanceData?.currentDate||attendanceData?.date;
        if(!selectedDate)throw Error('Choose an attendance date.');
        return {start:selectedDate,end:selectedDate}
    }
    if(!/^\d{4}-\d{2}$/.test(attendanceStartMonth)||!/^\d{4}-\d{2}$/.test(attendanceEndMonth))throw Error('Choose both a start and end month.');
    if(attendanceStartMonth>attendanceEndMonth)throw Error('The start month must not be after the end month.');
    let [startYear,startMonth]=attendanceStartMonth.split('-').map(Number),[endYear,endMonth]=attendanceEndMonth.split('-').map(Number);
    if(startMonth<1||startMonth>12||endMonth<1||endMonth>12)throw Error('Choose valid calendar months.');
    let start=`${attendanceStartMonth}-01`,end=new Date(Date.UTC(endYear,endMonth,0)).toISOString().slice(0,10),currentDate=attendanceData?.currentDate;
    if(currentDate&&end>currentDate)end=currentDate;
    if(currentDate&&start>currentDate)throw Error('The selected period cannot start in the future.');
    if(startYear===endYear&&startMonth===endMonth&&end<start)throw Error('The selected month has no attendance dates yet.');
    return {start,end}
}
async function loadSelectedAttendance(){
    let range=attendancePeriodRange();
    attendanceSyncStatus='Loading attendance…';
    render();
    await loadAttendanceData(range.start,range.end);
    attendanceSyncStatus='';
    if(page==='attendance')render(true)
}
async function loadAttendanceData(startDate,endDate){
    let sequence=++attendanceLoadSequence,path=startDate&&endDate?'/attendance?start='+encodeURIComponent(startDate)+'&end='+encodeURIComponent(endDate):'/attendance';
    let result=await directoryRequest(path);
    if(sequence!==attendanceLoadSequence)return;
    attendanceData=result;
    attendanceSelectedDate=result.date||result.currentDate;
    if(!attendanceStartMonth)attendanceStartMonth=result.currentDate.slice(0,7);
    if(!attendanceEndMonth)attendanceEndMonth=result.currentDate.slice(0,7);
    let changed=!startDate&&!endDate&&applyAttendanceScores(result);
    if(changed)await saveState()
}
async function syncAttendance(silent=true,selectedPeriod=null){
    if(!tenantAuthCsrfToken||document.hidden)return false;
    attendanceLastAttempt=Date.now();
    attendanceSyncStatus='Syncing BambooHR attendance…';
    let succeeded=false;
    try{
        let synced=await directoryRequest('/attendance/sync',{
            method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify(selectedPeriod||{})
        });
        if(selectedPeriod){
            attendanceData=synced;
            attendanceSelectedDate=synced.currentDate
        }
        else{
            if(applyAttendanceScores(synced))await saveState();
            let range=attendancePeriodRange();
            await loadAttendanceData(range.start,range.end)
        }
        attendanceSyncStatus='';
        succeeded=true;
        if(!silent)message('Attendance refreshed at '+new Date(synced.reportedAt).toLocaleTimeString()+'.');
    }
    catch(error){
        attendanceSyncStatus=error.message;
        if(!silent)message('Attendance sync failed: '+error.message,true)
    }
    if(page==='attendance')render(true)
    return succeeded
}
function startAttendancePolling(){
    if(attendanceSyncTimer)clearInterval(attendanceSyncTimer);
    attendanceSyncTimer=setInterval(()=>{
        if(!document.hidden&&Date.now()-attendanceLastAttempt>=5*60*1000)syncAttendance(true)
    },60*1000);
    document.addEventListener('visibilitychange',()=>{
        if(!document.hidden&&Date.now()-attendanceLastAttempt>=5*60*1000)syncAttendance(true)
    });
    syncAttendance(true)
}
async function loadBambooPublishStatus(){
    try{
        let response=await fetch('/api/bamboohr/status'),body=await response.json();
        if(!response.ok)throw Error(body.error||'BambooHR status request failed with HTTP '+response.status+'.');
        publishConfigured=body.configured===true;
        publishError=''
    }
    catch(error){
        publishConfigured=false;
        publishError=error.message
    }
}
function acceptedScheduleSnapshot(schedule){
    let snapshot=clone(schedule);
    for(let employee of snapshot.employees){
        let record=employeeDirectory.find(item=>item.id===String(employee.id));
        if(!record)continue;
        let location=scheduleLocations.find(item=>item.id===record.scheduleLocationId);
        Object.assign(employee,{
            bamboohrId:record.bamboohrId,scheduleLocationId:record.scheduleLocationId,
            active:record.active,directoryLocation:record.location,directoryRole:record.role,
            bambooScheduleId:location?.bambooScheduleId??null,
            scheduleLocationName:location?.name??null,scheduleRoleGroup:location?.roleGroup??null
        })
    }
    return snapshot
}
function heading(k,t,p){
    return `<header class="heading"><div><div class="eyebrow">${k}</div><h2>${t}</h2><p>${p}</p></div></header>`
}
function panel(t,body,note=''){
    return `<section class="panel"><h3>${t}</h3>${body}${note?`<p class="note">${note}</p>`:''}</section>`
}
function collapsiblePanel(key,t,body,note=''){
    return `<section class="panel collapsible"><details data-collapse-key="${esc(key)}" ${expandedPanels.has(key)?'open':''}><summary><h3>${t}</h3></summary><div class="panel-body">${body}${note?`<p class="note">${note}</p>`:''}</div></details></section>`
}
document.addEventListener('toggle',e=>{
    let key=e.target?.dataset?.collapseKey;
    if(!key)return;
    if(e.target.open)expandedPanels.add(key);else expandedPanels.delete(key)
},true);
function badge(t,status=''){
    return `<span class="badge ${status}">${esc(t)}</span>`
}
function stats(a){
    return '<div class="kpis">'+a.map(([l,v,t])=>`<article class="kpi"><small>${l}</small><strong>${v}</strong><span>${t}</span></article>`).join('')+'</div>'
}
function select(options,val,attrs=''){
    return `<select ${attrs}>${options.map(([v,t])=>`<option value="${esc(v)}" ${String(val??'')===String(v)?'selected':''}>${esc(t)}</option>`).join('')}</select>`
}
function disabled(){
    return model.locked?'disabled':''
}
async function nav(p){
    if(['source','meta'].includes(p)){
        try{await authorizeDataSettings();}
        catch(error){message(error.message,true);return;}
    }
    if(!pageAllowed(p)){
        message('This page is disabled. Enable it in Settings.',true);
        return;

    }
    page=p;
    closeAppMenu();
    render();
    if(p==='settings')loadAccessAccounts()
}
function closeAppMenu(){
    let menu=$('appMenu'),toggle=$('menuToggle');
    let wasOpen=menu?.classList.contains('menu-open');
    menu?.classList.remove('menu-open');
    toggle?.setAttribute('aria-expanded','false');
    toggle?.setAttribute('aria-label','Open navigation menu');
    if(wasOpen)scheduleHeaderCollapse()
}
function setAppMenuOpen(open){
    let menu=$('appMenu'),toggle=$('menuToggle');
    if(!menu||!toggle)return;
    if(open){
        clearTimeout(initialHeaderCollapseTimer);
        let header=document.querySelector('.top');
        menu.style.setProperty('--menu-top',(header?Math.ceil(header.getBoundingClientRect().bottom):72)+'px')
    }
    menu.classList.toggle('menu-open',open);
    toggle.setAttribute('aria-expanded',String(open));
    toggle.setAttribute('aria-label',open?'Close navigation menu':'Open navigation menu')
}
document.addEventListener('click',e=>{
    let toggle=e.target.closest('#menuToggle'),menu=$('appMenu');
    if(toggle){
        setAppMenuOpen(toggle.getAttribute('aria-expanded')!=='true');
        return
    }
    if(menu?.classList.contains('menu-open')&&!menu.contains(e.target))closeAppMenu()
});
document.addEventListener('keydown',e=>{
    if(e.key==='Escape')closeAppMenu()
});
window.matchMedia('(min-width: 851px)').addEventListener('change',closeAppMenu);
window.addEventListener('resize',()=>{
    if(window.innerWidth>850)closeAppMenu()
});
let initialHeaderCollapseTimer,lastHeaderScrollY=window.scrollY,lastTouchY=null,lastHeaderInputDirection=null,lastHeaderInputAt=0,ignoreHeaderScrollUntil=0;
function scheduleHeaderCollapse(){
    clearTimeout(initialHeaderCollapseTimer);
    if(!$('appMenu')?.classList.contains('menu-open'))initialHeaderCollapseTimer=setTimeout(()=>setHeaderCollapsed(true),5000)
}
function handleHeaderScrollDirection(down,fromInput=false){
    if(fromInput){
        lastHeaderInputDirection=down;
        lastHeaderInputAt=performance.now()
    }
    clearTimeout(initialHeaderCollapseTimer);
    if(down)setHeaderCollapsed(true);
    else{
        setHeaderCollapsed(false);
        scheduleHeaderCollapse()
    }
    requestAnimationFrame(()=>lastHeaderScrollY=window.scrollY)
}
function setHeaderCollapsed(collapsed){
    let header=document.querySelector('.top');
    if(!header)return;
    if(collapsed&&$('appMenu')?.classList.contains('menu-open'))return;
    if(header.classList.contains('header-collapsed')===collapsed)return;
    ignoreHeaderScrollUntil=performance.now()+1500;
    header.classList.toggle('header-collapsed',collapsed);
    if(collapsed)closeAppMenu();
    else if($('appMenu')?.classList.contains('menu-open'))setAppMenuOpen(true)
}
function initHeaderCollapse(){
    scheduleHeaderCollapse();
    window.addEventListener('wheel',e=>{
        if(e.deltaY)handleHeaderScrollDirection(e.deltaY>0,true)
    },{passive:true});
    window.addEventListener('touchstart',e=>{
        lastTouchY=e.touches[0]?.clientY??null
    },{passive:true});
    window.addEventListener('touchmove',e=>{
        let currentY=e.touches[0]?.clientY;
        if(currentY!==undefined&&lastTouchY!==null&&currentY!==lastTouchY)handleHeaderScrollDirection(currentY<lastTouchY,true);
        if(currentY!==undefined)lastTouchY=currentY
    },{passive:true});
    window.addEventListener('scroll',()=>{
        let currentY=window.scrollY;
        if(performance.now()<ignoreHeaderScrollUntil){
            lastHeaderScrollY=currentY;
            return
        }
        if(currentY!==lastHeaderScrollY){
            let down=currentY>lastHeaderScrollY;
            if(lastHeaderInputDirection!==null&&down!==lastHeaderInputDirection&&performance.now()-lastHeaderInputAt<1000){
                lastHeaderScrollY=currentY;
                return
            }
            let header=document.querySelector('.top');
            if(header?.classList.contains('header-collapsed')===down)handleHeaderScrollDirection(down)
        }
        lastHeaderScrollY=currentY
    },{passive:true})
}
function errorsPanel(){
    let issues=modelIssues(model);
    return `<div class="validation">${badge(issues.errors.length?issues.errors.length+' blocking issues':'Ready to lock',issues.errors.length?'bad':'good')} ${badge(issues.warnings.length+' warnings','warn')}<details ${issues.errors.length?'open':''}><summary>Review configuration checks</summary><ul>${issues.errors.map(e=>`<li class="badtext">${esc(e)}</li>`).join('')}${issues.warnings.map(e=>`<li>${esc(e)}</li>`).join('')}</ul></details></div>`
}
function home(){
    let p=model.pools.filter(p=>p.enabled),runs=model.results,missing=sum(runs.map(r=>r.uncovered.length)),short=sum(runs.map(r=>sum(r.shortages.map(e=>e.missing))));
    return heading('WORKFORCE PLANNING','Build the week. Protect the rules.','Configure your pools, validate employee constraints, lock the settings and generate a saved schedule for every selected week.')+stats([['Roster employees',f(model.roster.length),'Across source location-role pools'],['Enabled pools',p.length,'Of '+model.pools.length+' source pools'],['Planned weekly schedules',p.length*scheduleWeeks(model),'All enabled pools × '+scheduleWeeks(model)+' weeks'],['Saved schedules',runs.length,'Saved independently of later edits']])+`<div class="workflow">${[['01','Location roles','Set pools and shares','pools'],['02','Roster & META','Validate constraints','roster'],['03','Controls & lock','Set start, weeks and rules','controls'],['04','Generate & review','Inspect and download','schedules']].map(([n,t,d,g])=>`<button type="button" data-page="${g}"><small>${n}</small><b>${t}</b><span>${d}</span></button>`).join('')}</div>`+errorsPanel()+panel('Configuration status',`<p>${model.locked?'Settings are locked at revision '+model.revision+'. You can generate schedules from this snapshot.':'Settings are editable. Generation is disabled until validation passes and you lock the configuration.'}</p><div class="actions"><button type="button" class="primary" data-action="${model.locked?'generate':'lock'}">${model.locked?'Generate all schedules':'Validate & lock settings'}</button><button type="button" data-page="controls">Review controls</button></div>`)+ (runs.length?panel('Latest saved schedule review',stats([['Unfilled demand',missing,'Primary demand slots without an eligible employee'],['Employee target shortfall',short,'Missing employee shifts across saved weeks'],['Make-up shifts',sum(runs.map(r=>r.makeup)),'Additional to demand; marked separately']])):'')+panel('Model notes','<p>This app implements a demand-first scoring and make-up rules in browser code. It uses all shifts and checks permissions, daily availability, one shift per day, weekly shift limits and rest between actual shift intervals, including consecutive generated weeks.</p><p>Source input values drive the documented scheduling model. Missing inputs remain missing; review enabled-pool checks before generation.</p>')
}
function poolState(p){
    let rs=poolRoster(model,p),temp=clone(model);
    temp.pools.forEach(x=>x.enabled=x.id===p.id);
    let problems=modelIssues(temp).errors;
    return {
        count:rs.length,ready:problems.length===0,issues:problems
    }

}
function pools(){
    let rows=model.pools.map((p,i)=>{
        if(filterLoc!=='All'&&p.location!==filterLoc)return '';let st=poolState(p);return `<tr data-pool-row="${i}"><td><input type="checkbox" data-pool="${i}" data-field="enabled" ${p.enabled?'checked':''} ${disabled()} aria-label="Enable ${esc(p.id)}"></td><td>${esc(p.location)}</td><td>${esc(p.role)}</td><td>${st.count}</td><td><div class="shift-options">${poolStarts(p).map((s,j)=>`<span class="shift-option"><label>${timeLabel(s)}<input type="number" min="0" max="100" step="any" value="${percent(p.shares[j])}" data-pool="${i}" data-share="${j}" ${disabled()} aria-label="${timeLabel(s)} share for ${esc(p.id)}"></label><button type="button" class="shift-remove" data-action="removeShiftStart" data-pool-index="${i}" data-shift-start="${s}" ${disabled()} aria-label="Remove ${timeLabel(s)} from ${esc(p.id)}" title="Remove ${timeLabel(s)}">×</button></span>`).join('')}<label>Add start<input type="time" step="900" data-new-shift-start="${i}" ${disabled()} aria-label="New shift start for ${esc(p.id)}"></label><button type="button" data-action="addShiftStart" data-pool-index="${i}" ${disabled()}>Add</button></div></td><td>${!membershipFeatureEnabled('overtimeForecasting')?'<span class="note">Gold+</span>':warehouseRole(p.role)?'<span class="note">Volume-based</span>':`<input type="number" min="0" max="1000000000000" step="1" value="${esc(overtimeConfig().minimum[p.id]??'')}" data-ot-minimum="${esc(p.id)}" ${disabled()} aria-label="Minimum daily headcount for ${esc(p.id)}">`}</td><td title="${esc(st.issues.join('; '))}">${badge(st.count===0?'No roster':st.ready?'Ready':'Incomplete',st.ready?'good':'warn')}</td></tr>`
    }).filter(Boolean).join('');
    if(!rows)rows='<tr><td colspan="7">No location-role pools configured.</td></tr>';
    return heading('CONFIGURATION / LOCATION ROLES','Choose the pools to schedule.','Add or remove possible start times per location and role. New starts begin with 0% share; allocate their share here and set employee permissions in Roster settings.')+`<div class="toolbar"><label>Filter location ${select([['All','All locations'],...model.locations.map(l=>[l.name,l.name])],filterLoc,'id="poolLocation"')}</label><span>${model.locked?'Locked · unlock in Controls to edit':'Shift shares per pool must total 100%'}</span><button type="button" data-action="addAppLocation" ${model.locked||!tenantAuthPrimaryAdmin?'disabled':''}>Add location</button><button type="button" data-action="addLocationRole" ${model.locked||!tenantAuthPrimaryAdmin||!model.locations.length?'disabled':''}>Add role to location</button></div>`+panel('Location × role configuration',`<div class="tablewrap"><table><thead><tr><th>Enabled</th><th>Location</th><th>Role</th><th>HC</th><th>Possible starts · share %</th><th>Min daily HC<br>Other roles</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>`,'New starts default to 0% share and unavailable for every employee. Removing a start redistributes a valid share allocation across remaining starts. Each pool must keep at least one start, and any employee preference for that time must be changed before removing it.')+volumeConfiguration()+errorsPanel()
}
const ROSTER_FIELDS=[['flex','Flexible','list'],['reason','Reason if no','text'],['preferred','Preferred start','start'],['proximity','Proximity 1–3','rank'],['random','Random 1–3','rank'],['attendance','Attendance 0–100','number'],...DAYS.map((d,i)=>['day'+i,d,'binary'])];
function rosterFields(pool){
    return [...ROSTER_FIELDS.slice(0,6),...poolStarts(pool).map(s=>['start:'+s,'Allow '+timeLabel(s),'binary']),...ROSTER_FIELDS.slice(6)]
}
function rosterInput(e,i,k,type){
    let val=k.startsWith('start:')?e.shiftAvailability?.[String(Number(k.slice(6)))]:k.startsWith('day')?e.days[+k.slice(3)]:e[k],at=`data-employee="${i}" data-field="${k}" ${disabled()} aria-label="${esc(e.name+' '+k)}"`;
    if(type==='text')return `<input type="text" value="${esc(val)}" maxlength="240" ${at}>`;
    if(type==='number')return `<input type="number" min="0" max="100" step="any" value="${val??''}" ${at}>`;
    let employeePool=model.pools.find(p=>p.id===key(e.location,e.role)),opts=type==='list'?[['','Missing'],['Yes','Yes'],['No','No']]:type==='start'?[['','Missing'],...poolStarts(employeePool).map(s=>[s,timeLabel(s)])]:type==='rank'?[['','Missing'],[1,'1'],[2,'2'],[3,'3']]:[['','Missing'],[1,'1 · Yes'],[0,'0 · No']];
    return select(opts,val,at)
}
function sharedRosterPanel(){
    if(sharedRosterError)return panel('Shared roster unavailable',`<p class="badtext">${esc(sharedRosterError)}</p><button type="button" data-action="reloadSharedRoster">Retry</button>`);
    if(!sharedRoster?.configured){
        const unmapped=employeeDirectory.filter(employee=>!employee.location||!employee.role||!model.pools.some(pool=>pool.location===employee.location&&pool.role===employee.role));
        const ready=employeeDirectory.length>0&&!unmapped.length;
        return panel('Shared roster setup',`${tenantAuthPrimaryAdmin?`<p>${unmapped.length?`${unmapped.length} employee(s) still need an accepted location and a location-role assignment.`:'Directory profiles are ready to initialize.'}</p><button type="button" class="primary" data-action="initializeSharedRoster" ${ready?'':'disabled'}>Initialize from employee directory</button>`:'<p class="note">Ask the primary administrator to initialize shared roster settings.</p>'}`)
    }
    const missing=sharedRoster.employees.filter(employee=>!employee.settings);
    const assignableMissing=missing.filter(employee=>employee.location&&employee.role&&model.pools.some(pool=>pool.location===employee.location&&pool.role===employee.role));
    const unmappedMissing=missing.length-assignableMissing.length;
    const localPools=sharedRoster.pools.map(remote=>{
        const local=model.pools.find(pool=>pool.location===remote.location&&pool.role===remote.role);
        return !local||JSON.stringify(poolStarts(local).map(Number))!==JSON.stringify(remote.starts.map(Number))
    });
    const mismatch=localPools.some(Boolean);
    return panel('Shared roster',`<p>Shared settings are active · revision ${sharedRoster.revision} · ${sharedRoster.employees.filter(employee=>employee.settings).length} employee profiles.</p>${assignableMissing.length?`<p class="note">${assignableMissing.length} mapped employee profile(s) can be added without overwriting existing settings.</p><button type="button" data-action="syncSharedRosterEmployees" ${sharedRoster.locked?'disabled':''}>Preview and add ${assignableMissing.length} employee profile(s)</button>`:''}${unmappedMissing?`<p class="note">${unmappedMissing} employee(s) still need a location-role assignment before roster profiles can be added.</p>`:''}${mismatch?`<p class="note">Possible shift starts in this browser differ from the shared settings. ${sharedRoster.locked?'Unlock configuration before synchronizing them.':'Review and synchronize the current pool starts.'}</p><button type="button" data-action="syncSharedRosterPools" ${sharedRoster.locked?'disabled':''}>Preview and synchronize possible starts</button>`:''}${sharedRoster.locked?'<p class="note">Roster settings are locked and read-only.</p>':''}`)
}
function roster(){
    let shown=model.roster.map((e,i)=>({
        e,i
    }
    )).filter(({
        e
    }
    )=>(filterLoc==='All'||e.location===filterLoc)&&(filterRole==='All'||e.role===filterRole)&&(!search||(e.name+' '+e.id).toLowerCase().includes(search.toLowerCase())));
    let groups=model.pools.map(pool=>({pool,entries:shown.filter(({e})=>key(e.location,e.role)===pool.id)}    )).filter(group=>group.entries.length);
    return heading('PEOPLE / ROSTER','Respect employee constraints.','Set each employee’s availability for every configured shift start in their location-role pool. Inactive employees remain visible here but are excluded from schedules.')+sharedRosterPanel()+`<div class="toolbar"><label>Location ${select([['All','All locations'],...model.locations.map(l=>[l.name,l.name])],filterLoc,'id="rosterLocation"')}</label><label>Role ${select([['All','All roles'],...[...new Set(model.roster.map(e=>e.role))].sort().map(x=>[x,x])],filterRole,'id="rosterRole"')}</label><label>Find employee<input id="rosterSearch" placeholder="Name or ID" value="${esc(search)}"></label><span>${shown.length} employees</span></div>`+panel('Employee settings',groups.length?groups.map(({pool,entries})=>`<h3>${esc(pool.location)} · ${esc(pool.role)}</h3><div class="tablewrap rostergrid"><table><thead><tr><th>ID / Employee</th><th>Location / Role</th>${rosterFields(pool).map(([k,l])=>'<th>'+esc(l)+'</th>').join('')}<th>Validation</th></tr></thead><tbody>${entries.map(({e,i})=>`<tr data-roster-employee="${esc(e.id)}"><td class="sticky"><b>${esc(e.name)}</b><small>${esc(e.id)} · ${e.active===false?'Inactive':'Active'}</small></td><td>${esc(e.location)}<small>${esc(e.role)}</small></td>${rosterFields(pool).map(([k,l,t])=>'<td>'+rosterInput(e,i,k,t)+'</td>').join('')}<td>${rosterErrors(e).length?'<span class="badtext">'+esc(rosterErrors(e).join('; '))+'</span>':badge('Ready','good')}</td></tr>`).join('')}</tbody></table></div>`).join(''):'<p>No employee settings are available until locations and roles are configured.</p>','Source random scores remain editable. Attendance scores are editable snapshots; blank scores receive no top-three preference bonus. Availability is per shift start and employee, in addition to the daily availability fields.')
}
function allEmployeeRecords(){
    let records=employeeDirectory.map(employee=>({...employee,roster:model.roster.find(entry=>String(entry.id)===employee.id)||null}));
    let known=new Set(employeeDirectory.map(employee=>employee.id));
    for(let employee of model.roster)if(!known.has(String(employee.id)))records.push({
        id:String(employee.id),bamboohrId:employee.bamboohrId||'',name:employee.name,location:employee.location,role:employee.role,
        active:false,scheduleLocationId:employee.scheduleLocationId||null,roster:employee,source:'unregistered',unregistered:true
    });
    return records.sort((a,b)=>a.name.localeCompare(b.name))
}
function employeeDirectoryLocation(employee){
    return employee.location||employee.bamboohrLocation||''
}
function employeeProfileReady(employee){
    let pool=model.pools.find(item=>item.location===employee?.location&&item.role===employee?.role);
    return !!employee&&!!pool&&rosterErrors(employee).length===0&&poolStarts(pool).every(start=>[0,1].includes(employee.shiftAvailability?.[String(start)]))
}
function employeeRoleOptions(employee){
    let roles=[...new Set(model.pools.filter(pool=>pool.location===employee.location).map(pool=>pool.role))];
    if(employee.role&&!roles.includes(employee.role))roles.push(employee.role);
    return [['','Assign role'],...roles.sort().map(role=>[role,role])]
}
function employeesPage(){
    let allEmployees=allEmployeeRecords();
    let locations=[...new Set(allEmployees.map(employeeDirectoryLocation).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    let directoryRoles=[...new Set(allEmployees.map(employee=>employee.role).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    let unmappedLocation='__employee_unmapped__',unassignedRole='__employee_unassigned__';
    if(employeeLocationFilter!=='All'&&employeeLocationFilter!==unmappedLocation&&!locations.includes(employeeLocationFilter))employeeLocationFilter='All';
    if(employeeRoleFilter!=='All'&&employeeRoleFilter!==unassignedRole&&!directoryRoles.includes(employeeRoleFilter))employeeRoleFilter='All';
    let employees=allEmployees.filter(employee=>
        (employeeLocationFilter==='All'||(employeeLocationFilter===unmappedLocation?!employeeDirectoryLocation(employee):employeeDirectoryLocation(employee)===employeeLocationFilter))&&
        (employeeRoleFilter==='All'||(employeeRoleFilter===unassignedRole?!employee.role:employee.role===employeeRoleFilter))
    );
    let registeredEmployees=allEmployees.filter(employee=>!employee.unregistered);
    selectedEmployeeIds=new Set([...selectedEmployeeIds].filter(id=>registeredEmployees.some(employee=>employee.id===id)));
    let roles=[...new Set(model.pools.map(pool=>pool.role))].sort();
    return heading('PEOPLE / EMPLOYEES','BambooHR and manual employee directory.','Refresh imports active BambooHR employees without changing mapped roles or app locations. App active status is local to scheduling. Manually added employees are marked and never published to BambooHR.')+
        (directoryError?panel('Employee directory unavailable',`<p class="badtext">${esc(directoryError)}</p><button type="button" data-action="reloadDirectory">Retry</button>`):'')+
        `<div class="toolbar"><span>${allEmployees.length} employees · ${allEmployees.filter(employee=>employee.active).length} active for scheduling</span><button type="button" class="primary" data-action="syncBambooEmployees" ${publishConfigured?'':'disabled'}>Refresh BambooHR employees</button><button type="button" data-action="addEmployee" ${model.locked?'disabled':''}>Add manual employee</button></div>`+
        (employeeSyncStatus?`<p class="${employeeSyncStatus.startsWith('BambooHR sync failed')?'badtext':'note'}" role="status">${esc(employeeSyncStatus)}</p>`:'')+
        panel('Employee directory',`<div class="toolbar"><label>Location ${select([['All','All locations'],...locations.map(location=>[location,location]),...(allEmployees.some(employee=>!employeeDirectoryLocation(employee))?[[unmappedLocation,'Unmapped']]:[])],employeeLocationFilter,'id="employeeLocationFilter"')}</label><label>Role ${select([['All','All roles'],...directoryRoles.map(role=>[role,role]),...(allEmployees.some(employee=>!employee.role)?[[unassignedRole,'Unassigned']]:[])],employeeRoleFilter,'id="employeeRoleFilter"')}</label><span>${employees.length} of ${allEmployees.length} employees</span><span id="selectedEmployeeCount">${selectedEmployeeIds.size} selected</span><button type="button" data-action="batchEmployeeStatus" data-active="true" ${model.locked||!selectedEmployeeIds.size?'disabled':''}>Make active</button><button type="button" data-action="batchEmployeeStatus" data-active="false" ${model.locked||!selectedEmployeeIds.size?'disabled':''}>Make inactive</button><label>Assign role ${select([['','Choose role'],...roles.map(role=>[role,role])],'','id="batchEmployeeRole"')}</label><button type="button" data-action="batchEmployeeRole" ${model.locked||!selectedEmployeeIds.size?'disabled':''}>Assign to selected</button></div><div class="tablewrap"><table><thead><tr><th><input type="checkbox" data-employee-select-all aria-label="Select all visible employees"></th><th>App status</th><th>Source</th><th>Employee ID</th><th>BambooHR ID</th><th>Name</th><th>Location</th><th>Role</th><th>Schedule location</th><th>Roster profile</th><th>Actions</th></tr></thead><tbody>${employees.map(employee=>{
            let roster=employee.roster,ready=employeeProfileReady(roster),assigned=scheduleLocations.find(location=>location.id===employee.scheduleLocationId);
            let sourceBadge=employee.source==='manual'?badge('Manual','warn'):employee.source==='bamboohr'?badge('BambooHR','good'):badge('Not registered','warn');
            let bambooStatus=employee.source==='bamboohr'&&employee.bamboohrActive===false?'<small>BambooHR inactive · app scheduling disabled</small>':'';
            return `<tr><td><input type="checkbox" data-employee-select="${esc(employee.id)}" aria-label="Select ${esc(employee.name)}" ${selectedEmployeeIds.has(employee.id)?'checked':''} ${model.locked||employee.unregistered?'disabled':''}></td><td>${badge(employee.active?'Active':'Inactive',employee.active?'good':'warn')}${bambooStatus}</td><td>${sourceBadge}</td><td>${esc(employee.id)}</td><td>${esc(employee.bamboohrId||'Missing')}</td><td>${esc(employee.name)}</td><td>${esc(employee.location||employee.bamboohrLocation||'Unmapped')}</td><td>${select(employeeRoleOptions(employee),employee.role,`data-employee-role="${esc(employee.id)}" data-current-role="${esc(employee.role)}" ${model.locked||employee.unregistered?'disabled':''}`)}</td><td>${esc(assigned?.name||'Not assigned')}</td><td>${ready?badge('Ready','good'):badge(employee.unregistered?'Directory setup required':'Needs setup','warn')}</td><td><div class="actions employee-actions">${!employee.unregistered?`<button type="button" data-action="editEmployee" data-employee-id="${esc(employee.id)}">Edit</button><button type="button" data-action="editEmployeeProfile" data-employee-id="${esc(employee.id)}">${ready?'Roster settings':'Complete profile'}</button><button type="button" data-action="toggleEmployee" data-employee-id="${esc(employee.id)}" ${model.locked?'disabled':''}>${employee.active?'Make inactive':'Make active'}</button>${employee.source==='manual'?`<button type="button" class="danger" data-action="deleteEmployee" data-employee-id="${esc(employee.id)}" ${model.locked?'disabled':''}>Delete</button>`:''}`:'Not in directory'}</div></td></tr>`
        }).join('')}</tbody></table></div>`,'Profile settings are edited in Roster settings. New or imported employees should remain inactive until their roster profile is complete.')
}
function updateEmployeeSelectionUI(){
    let selectAll=$('#content [data-employee-select-all]'),count=$('selectedEmployeeCount');
    let selectedCount=selectedEmployeeIds.size;
    if(count)count.textContent=selectedCount+' selected';
    for(let button of document.querySelectorAll('#content [data-action="batchEmployeeStatus"]'))button.disabled=model.locked||!selectedCount;
    if(selectAll){
        let visibleInputs=[...document.querySelectorAll('#content [data-employee-select]')].filter(input=>!input.disabled);
        let selectedVisible=visibleInputs.filter(input=>input.checked).length;
        selectAll.checked=visibleInputs.length>0&&selectedVisible===visibleInputs.length;
        selectAll.indeterminate=selectedVisible>0&&selectedVisible<visibleInputs.length
    }
    let roleButton=$('#content [data-action="batchEmployeeRole"]');
    if(roleButton)roleButton.disabled=model.locked||!selectedCount
}
function normalizedEmployeeKey(value){
    return String(value||'').trim().toLowerCase()
}
async function saveEmployeeRoleChanges(employeeIds,role){
    if(model.locked)throw Error('Unlock settings in Controls before changing employee roles.');
    if(!role)throw Error('Choose a role before assigning it.');
    let employees=employeeDirectory.filter(employee=>employeeIds.includes(employee.id));
    if(!employees.length||employees.length!==employeeIds.length)throw Error('One or more selected employees are no longer in the directory.');
    for(let employee of employees){
        if(!model.pools.some(pool=>pool.location===employee.location&&pool.role===role))throw Error(`Create a ${employee.location} · ${role} Location Roles pool before assigning this role.`);
        let location=scheduleLocations.find(item=>item.id===employee.scheduleLocationId);
        if(location&&!roleFitsScheduleGroup(role,location))throw Error(`The role ${role} does not match ${employee.name}'s schedule location. Change the schedule location first.`)
    }
    let changed=employees.filter(employee=>employee.role!==role);
    if(!changed.length)return 0;
    await directoryRequest('/employees/roles',{method:'PUT',body:JSON.stringify({employeeIds:employees.map(employee=>employee.id),role})});
    for(let employee of changed){
        let index=model.roster.findIndex(entry=>String(entry.id)===employee.id);
        if(index<0)continue;
        model.roster[index]=blankRosterProfile({...employee,role,active:false},index)
    }
    await loadDirectoryData();
    await saveState();
    render(true);
    return changed.length
}
function applyEmployeeIdChanges(changes){
    for(let change of changes||[]){
        let matching=change.bamboohrId?model.roster.find(employee=>employee.bamboohrId===change.bamboohrId):null;
        let oldProfile=model.roster.find(employee=>String(employee.id)===String(change.oldId));
        if(change.mergedManualId){
            let manualProfile=model.roster.find(employee=>String(employee.id)===String(change.mergedManualId));
            let existingProfile=matching||oldProfile;
            let keep=manualProfile&&(!existingProfile||employeeProfileReady(manualProfile)&&!employeeProfileReady(existingProfile))?manualProfile:existingProfile||manualProfile;
            model.roster=model.roster.filter(employee=>employee!==manualProfile&&employee!==existingProfile);
            if(keep){
                keep.id=change.newId;
                model.roster.push(keep)
            }
        }
        else if(change.source==='manual'&&oldProfile)oldProfile.id=change.newId;
        else if(change.source==='bamboohr'&&(matching||oldProfile))(matching||oldProfile).id=change.newId
    }
    model.roster.forEach((employee,index)=>employee.index=index)
}
async function finishBambooEmployeeSync(result){
    applyEmployeeIdChanges(result.employeeIdChanges);
    await loadDirectoryData();
    let persisted=await saveState(),directoryReloadError=directoryError;
    pendingEmployeeSyncConflicts=[];
    $('employeeSyncDialog')?.close();
    employeeSyncStatus=`BambooHR sync complete · ${result.synced} active records checked, ${result.added} added, ${result.updated} refreshed, ${result.merged} duplicate(s) merged, ${result.rekeyed} Employee ID(s) updated, ${result.inactivated} locally deactivated.`;
    render(true);
    message(directoryReloadError?`BambooHR sync completed, but the employee directory could not be refreshed: ${directoryReloadError}`:persisted?'BambooHR employee directory synchronized. Review new or unmapped employees and assign their roles.':'BambooHR employee directory synchronized for this session. Download a workspace backup to preserve roster changes.',!!directoryReloadError);
    if(!directoryReloadError){
        const known=new Set(model.locations.map(location=>location.name.toLowerCase()));
        const candidates=[...new Map(employeeDirectory.map(employee=>String(employee.bamboohrLocation||'').trim()).filter(name=>name&&!known.has(name.toLowerCase())).map(name=>[name.toLowerCase(),name])).values()];
        if(candidates.length){
            if(tenantAuthPrimaryAdmin)openBambooLocationAcceptanceDialog(candidates);
            else message('New BambooHR locations were found. Ask the primary administrator to accept them before assigning roles.')
        }
    }
}
async function requestBambooEmployeeSync(resolutions=[]){
    let result=await directoryRequest('/bamboohr/employees/sync',{method:'POST',body:JSON.stringify({resolutions})});
    if(result.requiresReview){
        openEmployeeSyncReview(result.conflicts);
        employeeSyncStatus=`${result.conflicts.length} possible duplicate(s) need review. No employee records were changed.`;
        render(true);
        return
    }
    await finishBambooEmployeeSync(result)
}
function openBambooLocationAcceptanceDialog(candidates){
    const dialog=workflowDialog('bambooLocationAcceptanceDialog');
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">BAMBOOHR EMPLOYEE DIRECTORY</div><h2>Accept locations</h2></div><button type="button" data-dialog-close="bambooLocationAcceptanceDialog" aria-label="Close">Close</button></div><p>Select which BambooHR locations to add to Location Roles and META.</p><label class="check"><input type="checkbox" data-location-select-all checked> Accept all locations</label><div class="assignment-list">${candidates.map(name=>`<label><input type="checkbox" data-bamboo-location="${esc(name)}" checked><span>${esc(name)}</span></label>`).join('')}</div><div class="actions"><button type="button" data-dialog-close="bambooLocationAcceptanceDialog">Not now</button><button type="button" class="primary" data-action="acceptBambooLocations">Accept selected locations</button></div>`;
    const all=dialog.querySelector('[data-location-select-all]');
    dialog.querySelectorAll('[data-bamboo-location]').forEach(input=>input.addEventListener('change',()=>{
        const boxes=[...dialog.querySelectorAll('[data-bamboo-location]')];
        all.checked=boxes.every(box=>box.checked);
        all.indeterminate=boxes.some(box=>box.checked)&&!all.checked
    }));
    all.addEventListener('change',()=>dialog.querySelectorAll('[data-bamboo-location]').forEach(input=>input.checked=all.checked));
    if(!dialog.open)dialog.showModal()
}
async function acceptSelectedBambooLocations(){
    const dialog=$('bambooLocationAcceptanceDialog');
    const names=[...dialog.querySelectorAll('[data-bamboo-location]:checked')].map(input=>input.dataset.bambooLocation);
    if(!names.length)throw Error('Select at least one BambooHR location.');
    if(model.locked)throw Error('Unlock settings in Controls before accepting locations.');
    await loadSharedMetaSettings();
    if(!sharedMeta?.configured&&model.locations.length){
        const initialized=await acceptLocationsOnServer('workbook',model.locations.map(location=>({
            name:location.name,intensity:location.intensity,open:location.open
        })));
        applyAcceptedLocations(initialized)
    }
    const result=await acceptLocationsOnServer('bamboohr',names);
    applyAcceptedLocations(result);
    await loadDirectoryData();
    await saveState();
    dialog.close();
    render(true);
    message(`${result.accepted.length} new location(s) accepted. Employees with no app location were assigned from BambooHR; existing app assignments were preserved.`)
}
function workflowDialog(id){
    let dialog=$(id);
    if(!dialog){
        dialog=document.createElement('dialog');
        dialog.id=id;
        dialog.className='wide-dialog';
        document.body.append(dialog)
    }
    return dialog
}
function openEmployeeSyncReview(conflicts){
    pendingEmployeeSyncConflicts=conflicts;
    let dialog=workflowDialog('employeeSyncDialog');
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">EMPLOYEE RECONCILIATION</div><h2>Review possible duplicate employees</h2></div><button type="button" data-dialog-close="employeeSyncDialog" aria-label="Close">✕</button></div><p>These manual records share an Employee ID with a BambooHR record. Confirm whether each pair is the same person. No changes will be made until you confirm.</p>${conflicts.map((conflict,index)=>`<section class="panel"><h3>${esc(conflict.manualEmployee.name)} · ${esc(conflict.manualEmployee.id)}</h3><p>BambooHR: ${esc(conflict.bamboohrName)} · Employee ID ${esc(conflict.employeeId)}${conflict.existingBambooEmployeeId?` · existing BambooHR Employee ID ${esc(conflict.existingBambooEmployeeId)}`:''}</p><label><input type="radio" name="sync-person-${index}" value="same" checked> Same person — keep the BambooHR record and retain available app mappings</label><label><input type="radio" name="sync-person-${index}" value="different"> Different people — keep both records</label><label>New Employee ID for the manual employee<input data-sync-new-id="${index}" maxlength="80" value="" placeholder="Required if these are different people"></label></section>`).join('')}<div class="actions"><button type="button" data-dialog-close="employeeSyncDialog">Cancel</button><button type="button" class="primary" data-action="resolveBambooEmployeeSync">Confirm and sync</button></div>`;
    if(!dialog.open)dialog.showModal()
}
function sourceRoleOptions(workspace,location){
    let roles=[...new Set(workspace.pools.filter(pool=>pool.location===location).map(pool=>pool.role))].sort();
    return [['','Select role'],...roles.map(role=>[role,role])]
}
function updateSourceReviewRow(index){
    let row=sourceReviewRows[index],dialog=$('sourceImportReviewDialog');
    if(!row||!dialog)return;
    let location=dialog.querySelector(`[data-import-location="${index}"]`)?.value||'';
    let roleSelect=dialog.querySelector(`[data-import-role="${index}"]`),scheduleSelect=dialog.querySelector(`[data-import-schedule="${index}"]`);
    if(roleSelect){
        let current=roleSelect.value;
        roleSelect.innerHTML=sourceRoleOptions(pendingSourceImport,location).map(([value,label])=>`<option value="${esc(value)}" ${current===value?'selected':''}>${esc(label)}</option>`).join('');
        if(![...roleSelect.options].some(option=>option.value===current))roleSelect.value=''
    }
    if(scheduleSelect){
        let role=roleSelect?.value||'',prior=scheduleSelect.value;
        scheduleSelect.innerHTML=`<option value="">Not assigned</option>${scheduleLocations.filter(item=>item.location===location&&roleFitsScheduleGroup(role,item)).map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
        if([...scheduleSelect.options].some(option=>option.value===prior))scheduleSelect.value=prior
    }
}
function openSourceImportReview(workspace){
    pendingSourceImport=workspace;
    let currentById=new Map(employeeDirectory.map(employee=>[normalizedEmployeeKey(employee.id),employee]));
    sourceReviewRows=workspace.roster.map(profile=>{
        let existing=currentById.get(normalizedEmployeeKey(profile.id)),locationNames=new Set(workspace.locations.map(location=>location.name));
        let location=existing&&locationNames.has(existing.location)?existing.location:locationNames.has(profile.location)?profile.location:'';
        let roleOptions=workspace.pools.filter(pool=>pool.location===location).map(pool=>pool.role);
        let role=existing&&roleOptions.includes(existing.role)?existing.role:roleOptions.includes(profile.role)?profile.role:'';
        let scheduleLocationId=existing?.scheduleLocationId||'';
        if(!scheduleLocations.some(item=>item.id===scheduleLocationId&&item.location===location&&roleFitsScheduleGroup(role,item)))scheduleLocationId='';
        return {profile,existing,location,role,scheduleLocationId,addManual:false}
    });
    let dialog=workflowDialog('sourceImportReviewDialog');
    dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">SOURCE WORKBOOK</div><h2>Review employee mappings</h2></div><button type="button" data-dialog-close="sourceImportReviewDialog" aria-label="Close">✕</button></div><p>Review every employee's app location and role before importing. Existing BambooHR/manual mappings are preselected and retain their current role when it is available. Select Add manually only for unknown people who should be added to this app.</p><div class="tablewrap"><table><thead><tr><th>Employee</th><th>Source</th><th>Location</th><th>Role</th><th>Schedule location</th><th>New manual employee</th></tr></thead><tbody>${sourceReviewRows.map((row,index)=>{
        let source=row.existing?row.existing.source==='manual'?'Manual':'BambooHR':'Unknown';
        let roles=sourceRoleOptions(workspace,row.location),locations=workspace.locations.map(item=>[item.name,item.name]);
        let schedules=scheduleLocations.filter(item=>item.location===row.location&&roleFitsScheduleGroup(row.role,item)).map(item=>[item.id,item.name]);
        return `<tr><td>${esc(row.profile.name)}<small>Employee ID ${esc(row.profile.id)}</small></td><td>${badge(source,row.existing?'good':'warn')}${row.existing?`<small>Current: ${esc(row.existing.location)} · ${esc(row.existing.role||'No role')}</small>`:''}</td><td>${select([['','Select location'],...locations],row.location,`data-import-location="${index}"`)}</td><td>${select(roles,row.role,`data-import-role="${index}"`)}</td><td>${select([['','Not assigned'],...schedules],row.scheduleLocationId,`data-import-schedule="${index}"`)}</td><td>${row.existing?'—':`<label><input type="checkbox" data-import-manual="${index}"> Add manually</label>`}</td></tr>`
    }).join('')}</tbody></table></div><div class="actions"><button type="button" data-dialog-close="sourceImportReviewDialog">Cancel import</button><button type="button" class="primary" data-action="approveSourceImport">Approve mappings and import</button></div>`;
    dialog.querySelectorAll('[data-import-location],[data-import-role]').forEach(select=>select.addEventListener('change',()=>updateSourceReviewRow(Number(select.dataset.importLocation??select.dataset.importRole))));
    dialog.showModal()
}
async function approveSourceImportMappings(){
    await authorizeDataSettings('source-import');
    let workspace=pendingSourceImport,dialog=$('sourceImportReviewDialog');
    if(!workspace||!dialog)throw Error('The pending source workbook review could not be found.');
    let mappings=sourceReviewRows.map((row,index)=>{
        let location=dialog.querySelector(`[data-import-location="${index}"]`)?.value||'';
        let role=dialog.querySelector(`[data-import-role="${index}"]`)?.value||'';
        let scheduleLocationId=dialog.querySelector(`[data-import-schedule="${index}"]`)?.value||null;
        let addManual=!!dialog.querySelector(`[data-import-manual="${index}"]`)?.checked;
        if(!location||!role||!workspace.pools.some(pool=>pool.location===location&&pool.role===role))throw Error(`Choose a valid Location Roles mapping for ${row.profile.name}.`);
        if(scheduleLocationId&&!scheduleLocations.some(item=>item.id===scheduleLocationId&&item.location===location&&roleFitsScheduleGroup(role,item)))throw Error(`Choose a schedule location that matches ${row.profile.name}'s location and role.`);
        return {id:row.existing?.id||String(row.profile.id),name:row.existing?.name||String(row.profile.name),location,role,scheduleLocationId,addManual}
    });
    if(workspace.locations.length){
        const accepted=await acceptLocationsOnServer('workbook',workspace.locations.map(location=>({
            name:location.name,intensity:location.intensity,open:location.open
        })));
        applyAcceptedLocations(accepted,workspace,true)
    }
    let result=mappings.length?await directoryRequest('/employees/import-review',{method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify({employees:mappings})}):{addedManual:0,deactivated:0};
    let mappedById=new Map(mappings.map(mapping=>[normalizedEmployeeKey(mapping.id),mapping]));
    workspace.roster=workspace.roster.map(profile=>{
        let mapping=mappedById.get(normalizedEmployeeKey(profile.id));
        if(!mapping){
            profile.active=false;
            return profile
        }
        let prior=mapping.id===String(profile.id)?employeeDirectory.find(employee=>employee.id===mapping.id):employeeDirectory.find(employee=>normalizedEmployeeKey(employee.id)===normalizedEmployeeKey(mapping.id));
        profile.id=mapping.id;
        profile.name=mapping.name;
        profile.location=mapping.location;
        profile.role=mapping.role;
        profile.scheduleLocationId=mapping.scheduleLocationId;
        profile.bamboohrId=prior?.bamboohrId||'';
        profile.active=!!prior?.active&&prior.location===mapping.location&&prior.role===mapping.role;
        profile.sourceType=prior?.source|| (mapping.addManual?'manual':'unregistered');
        return profile
    });
    workspace.roster.forEach((profile,index)=>profile.index=index);
    model=workspace;
    await loadDirectoryData();
    let persisted=await saveState(),directoryReloadError=directoryError;
    pendingSourceImport=null;
    sourceReviewRows=[];
    dialog.close();
    page='home';
    filterLoc=filterRole='All';
    search='';
    render();
    message(directoryReloadError?`Source mappings were approved and imported, but the employee directory could not be refreshed: ${directoryReloadError}`:persisted?`Source workbook imported after review. ${result.addedManual||0} manual employee(s) added; ${result.deactivated||0} employee(s) deactivated for changed mappings.`:'Source workbook imported for this session. Download a workspace backup before closing.',!!directoryReloadError)
}
function scheduleLocationsPage(){
    return heading('PEOPLE / SCHEDULE LOCATIONS','Connect app locations to BambooHR schedules.','Each schedule location maps a name and app location to one BambooHR schedule ID. Employees can be assigned to only one schedule location at a time.')+
        (directoryError?panel('Schedule location directory unavailable',`<p class="badtext">${esc(directoryError)}</p><button type="button" data-action="reloadDirectory">Retry</button>`):'')+
        `<div class="toolbar"><span>${scheduleLocations.length} schedule locations</span><button type="button" class="primary" data-action="addScheduleLocation">Add schedule location</button></div>`+
        panel('Schedule location directory',`<div class="tablewrap"><table><thead><tr><th>Schedule name</th><th>BambooHR schedule ID</th><th>App location</th><th>Confirmation manager</th><th>Employees</th><th>Actions</th></tr></thead><tbody>${scheduleLocations.map(location=>`<tr><td>${esc(location.name)}<small>${esc(location.roleGroup)}</small></td><td>${esc(location.bambooScheduleId)}</td><td>${esc(location.location)}</td><td>${esc(location.managerName||'Manager not set')}<small>${esc(location.managerEmail||'')}</small></td><td>${location.employeeCount}</td><td><div class="actions"><button type="button" data-action="assignEmployees" data-location-id="${esc(location.id)}">Assign employees</button><button type="button" data-action="editScheduleLocation" data-location-id="${esc(location.id)}">Edit</button><button type="button" class="danger" data-action="deleteScheduleLocation" data-location-id="${esc(location.id)}">Delete</button></div></td></tr>`).join('')}</tbody></table></div>`,'The manager receives schedule confirmation drafts for this schedule location. Enter manager contact details before preparing emails. Employees moved to a schedule location inherit its app location; their required role is preserved. A schedule location with assigned employees cannot be deleted.')
}
function openAppLocationDialog(){
    if(model.locked)throw Error('Unlock settings in Controls before adding a location.');
    if(!tenantAuthPrimaryAdmin)throw Error('Only the primary administrator can add locations.');
    const dialog=workflowDialog('appLocationDialog');
    dialog.innerHTML=`<form id="appLocationForm"><div class="dialoghead"><h2>Add planning location</h2><button type="button" data-dialog-close="appLocationDialog" aria-label="Close">Close</button></div><label>Location name<input name="name" maxlength="240" required></label><div class="actions"><button type="button" data-dialog-close="appLocationDialog">Cancel</button><button type="submit" class="primary">Add location</button></div></form>`;
    dialog.querySelector('#appLocationForm').addEventListener('submit',async event=>{
        event.preventDefault();
        try{
            const name=String(new FormData(event.currentTarget).get('name')||'').trim();
            if(!name)throw Error('Enter a location name.');
            if(model.locations.some(location=>location.name.toLowerCase()===name.toLowerCase()))throw Error('That location already exists.');
            const result=await acceptLocationsOnServer('manual',[
                ...model.locations.map(location=>({name:location.name,intensity:location.intensity,open:location.open})),
                {name,intensity:[null,null,null,null,null,null,null],open:[null,null,null,null,null,null,null]}
            ]);
            applyAcceptedLocations(result);
            await saveState();
            dialog.close();
            render(true);
            message(`Location ${name} added to Location Roles and META.`)
        }catch(error){message(error.message,true)}
    });
    if(!dialog.open)dialog.showModal()
}
function openLocationRoleDialog(){
    if(model.locked)throw Error('Unlock settings in Controls before adding a role.');
    if(!tenantAuthPrimaryAdmin)throw Error('Only the primary administrator can add roles to locations.');
    if(!model.locations.length)throw Error('Add or accept a location first.');
    const dialog=workflowDialog('locationRoleDialog');
    const roles=[...new Set(model.pools.map(pool=>pool.role))].sort((a,b)=>a.localeCompare(b));
    dialog.innerHTML=`<form id="locationRoleForm"><div class="dialoghead"><h2>Add role to location</h2><button type="button" data-dialog-close="locationRoleDialog" aria-label="Close">Close</button></div><label>Location ${select(model.locations.map(location=>[location.name,location.name]),model.locations[0].name,'name="location" required')}</label><label>Existing or new role<input name="role" maxlength="240" list="existingLocationRoles" required><datalist id="existingLocationRoles">${roles.map(role=>`<option value="${esc(role)}">`).join('')}</datalist></label><div class="actions"><button type="button" data-dialog-close="locationRoleDialog">Cancel</button><button type="submit" class="primary">Add role to location</button></div></form>`;
    dialog.querySelector('#locationRoleForm').addEventListener('submit',async event=>{
        event.preventDefault();
        try{
            const values=new FormData(event.currentTarget),location=String(values.get('location')||''),role=String(values.get('role')||'').trim();
            if(!model.locations.some(item=>item.name===location))throw Error('Choose an existing location.');
            if(!role)throw Error('Enter or select a role.');
            if(model.pools.some(pool=>pool.location.toLowerCase()===location.toLowerCase()&&pool.role.toLowerCase()===role.toLowerCase()))throw Error('That role is already assigned to this location.');
            const pool={id:key(location,role),location,role,shiftStarts:[...STARTS],shares:[1,0,0,0],enabled:false,row:model.pools.length+7};
            if(sharedRoster?.configured){
                if(sharedRoster.locked)throw Error('Unlock roster settings before adding a location-role pool.');
                await saveSharedRosterConfiguration(false,[...sharedRoster.pools.map(item=>clone(item)),{location,role,starts:[...STARTS]}])
            }
            model.pools.push(pool);
            model.controls.location=location;
            model.controls.role=role;
            await saveState();
            dialog.close();
            render(true);
            message(`Role ${role} added to ${location}.`)
        }catch(error){message(error.message,true)}
    });
    if(!dialog.open)dialog.showModal()
}
function openEmployeeForm(employeeId=''){
    let existing=allEmployeeRecords().find(employee=>employee.id===employeeId),dialog=$('employeeDialog'),employee=existing||{
        id:'',bamboohrId:'',name:'',location:model.locations[0]?.name||'',role:'',active:false,scheduleLocationId:''
    };
    let isManual=employee.source==='manual'||!existing,roles=[...new Set(model.pools.map(item=>item.role))].sort(),locations=model.locations.map(item=>[item.name,item.name]);
    dialog.innerHTML=`<form id="employeeForm"><div class="dialoghead"><div><div class="eyebrow">EMPLOYEE DIRECTORY</div><h2>${existing?'Edit employee': 'Add manual employee'}</h2></div><button type="button" data-dialog-close="employeeDialog" aria-label="Close">✕</button></div><div class="formgrid"><label>Employee ID<input name="id" required maxlength="80" value="${esc(employee.id)}" ${!isManual?'readonly':''}></label><label>BambooHR ID<input name="bamboohrId" readonly value="${esc(employee.bamboohrId||'Assigned automatically for manual employees')}"></label><label>Employee name<input name="name" required maxlength="240" value="${esc(employee.name)}" ${!isManual?'readonly':''}></label><label>Location ${select(locations,employee.location,'name="location" required')}</label><label>Role ${select([['','Select role'],...roles.map(role=>[role,role])],employee.role,'name="role" required')}</label><label>Schedule location ${select([['','Not assigned'],...scheduleLocations.filter(item=>item.location===employee.location&&roleFitsScheduleGroup(employee.role,item)).map(item=>[item.id,item.name])],employee.scheduleLocationId||'','name="scheduleLocationId" '+(!existing?'disabled':'') )}</label><label class="setting-row"><input type="checkbox" name="active" ${employee.active?'checked':''} ${!existing?'disabled':''}><span><b>Active for scheduling</b><small>${existing?'App-only status; it does not change BambooHR.':'New manual employees start inactive.'}</small></span></label></div><p class="note">${existing?.source==='bamboohr'?'BambooHR ID, Employee ID, and name are read-only and refreshed from BambooHR.':'Manual employees receive an app-generated dummy BambooHR ID and are never published to BambooHR.'} Active status requires a complete roster profile. Role and location must match a source Location Roles pool.</p><div class="actions"><button type="button" data-dialog-close="employeeDialog">Cancel</button><button class="primary" type="submit">Save employee</button></div></form>`;
    dialog.showModal();
    let refreshScheduleLocations=()=>{
        let current=dialog.querySelector('select[name="scheduleLocationId"]'),chosen=scheduleLocations.find(item=>item.id===current.value);
        let selectedLocation=dialog.querySelector('select[name="location"]').value,selectedRole=dialog.querySelector('select[name="role"]').value;
        current.innerHTML=`<option value="">Not assigned</option>${scheduleLocations.filter(item=>item.location===selectedLocation&&roleFitsScheduleGroup(selectedRole,item)).map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
        if(chosen?.location===selectedLocation&&roleFitsScheduleGroup(selectedRole,chosen))current.value=chosen.id
    };
    dialog.querySelector('select[name="location"]').addEventListener('change',refreshScheduleLocations);
    dialog.querySelector('select[name="role"]').addEventListener('change',refreshScheduleLocations);
    dialog.querySelector('#employeeForm').addEventListener('submit',async event=>{
        event.preventDefault();
        try{
            await saveEmployeeForm(employee.id)
        }
        catch(error){
            message(error.message,true)
        }
    })
}
function openScheduleLocationForm(locationId=''){
    let existing=scheduleLocations.find(location=>location.id===locationId),dialog=$('scheduleLocationDialog'),location=existing||{
        id:'',name:'',bambooScheduleId:'',location:model.locations[0]?.name||'',roleGroup:'',managerName:'',managerEmail:''
    };
    dialog.innerHTML=`<form id="scheduleLocationForm"><div class="dialoghead"><div><div class="eyebrow">BAMBOOHR SCHEDULE</div><h2>${existing?'Edit schedule location':'Add schedule location'}</h2></div><button type="button" data-dialog-close="scheduleLocationDialog" aria-label="Close">✕</button></div><div class="formgrid"><label>Schedule name<input name="name" required maxlength="240" value="${esc(location.name)}"></label><label>BambooHR schedule ID<input name="bambooScheduleId" required maxlength="120" value="${esc(location.bambooScheduleId)}"></label><label>App location ${select(model.locations.map(item=>[item.name,item.name]),location.location,'name="location" required')}</label><label>Role group / description<input name="roleGroup" maxlength="120" value="${esc(location.roleGroup)}"></label><label>Manager name<input name="managerName" required maxlength="120" value="${esc(location.managerName)}"></label><label>Manager email<input name="managerEmail" type="email" required maxlength="254" value="${esc(location.managerEmail)}"></label></div><div class="actions"><button type="button" data-dialog-close="scheduleLocationDialog">Cancel</button><button class="primary" type="submit">Save schedule location</button></div></form>`;
    dialog.showModal();
    dialog.querySelector('#scheduleLocationForm').addEventListener('submit',async event=>{
        event.preventDefault();
        try{
            await saveScheduleLocationForm(location.id)
        }
        catch(error){
            message(error.message,true)
        }
    })
}
function renderAssignmentDialog(){
    let target=scheduleLocations.find(location=>location.id===assignLocationId);
    if(!target)return;
    let active=employeeDirectory.filter(employee=>employee.active),byId=new Map(active.map(employee=>[employee.id,employee]));
    let candidates=active.filter(employee=>!assignEmployeeIds.has(employee.id));
    $('assignEmployeesDialog').innerHTML=`<div class="dialoghead"><div><div class="eyebrow">EMPLOYEE ASSIGNMENTS</div><h2>Assign employees · ${esc(target.name)}</h2></div><button type="button" data-dialog-close="assignEmployeesDialog" aria-label="Close">✕</button></div><p>Choose active employees on the left, move them into the staged assignment on the right, then save. Changes are not applied until Save.</p><div class="assignment-split"><section><h3>All active employees · current mapping</h3><div class="assignment-list">${candidates.map(employee=>{
        let eligible=roleFitsScheduleGroup(employee.role,target)&&model.pools.some(pool=>pool.location===target.location&&pool.role===employee.role);
        return `<label><input type="checkbox" data-assignment-candidate="${esc(employee.id)}" ${assignCandidateIds.has(employee.id)?'checked':''} ${eligible?'':'disabled'}><span><b>${esc(employee.name)}</b><small>${esc(employee.id)} · ${esc(employee.location)} · ${esc(employee.role)} · ${esc(scheduleLocations.find(item=>item.id===employee.scheduleLocationId)?.name||'Unassigned')}${eligible?'':' · Role/location pool mismatch'}</small></span></label>`
    }).join('')||'<p>All active employees are already selected for this schedule location.</p>'}</div></section><div class="assignment-arrows"><button type="button" data-action="stageEmployees" aria-label="Move selected employees right">»</button><button type="button" data-action="unstageEmployees" aria-label="Move selected employees left">«</button></div><section><h3>Selected for ${esc(target.name)} · ${assignEmployeeIds.size}</h3><div class="assignment-list">${[...assignEmployeeIds].map(id=>byId.get(id)).filter(Boolean).map(employee=>`<label><input type="checkbox" data-assignment-selected="${esc(employee.id)}" ${assignCandidateIds.has(employee.id)?'checked':''}><span><b>${esc(employee.name)}</b><small>${esc(employee.id)} · ${esc(employee.location)} · ${esc(employee.role)}</small></span></label>`).join('')||'<p>No employees selected for this location yet.</p>'}</div></section></div><div class="actions"><button type="button" data-dialog-close="assignEmployeesDialog">Cancel</button><button type="button" class="primary" data-action="saveAssignments">Save assignments</button></div>`;
    $('assignEmployeesDialog').querySelectorAll('[data-assignment-candidate]').forEach(input=>input.addEventListener('change',()=>{
        input.checked?assignCandidateIds.add(input.dataset.assignmentCandidate):assignCandidateIds.delete(input.dataset.assignmentCandidate)
    }));
    $('assignEmployeesDialog').querySelectorAll('[data-assignment-selected]').forEach(input=>input.addEventListener('change',()=>{
        input.checked?assignCandidateIds.add(input.dataset.assignmentSelected):assignCandidateIds.delete(input.dataset.assignmentSelected)
    }))
}
async function saveEmployeeForm(originalId){
    if(model.locked)throw Error('Unlock settings in Controls before changing employees.');
    let form=$('employeeForm'),values=new FormData(form),id=String(values.get('id')).trim(),registered=originalId?employeeDirectory.find(entry=>entry.id===String(originalId)):null,bamboohrId=registered?.bamboohrId||'';
    let employee={
        id,bamboohrId,name:String(values.get('name')).trim(),location:String(values.get('location')),
        role:String(values.get('role')),active:values.get('active')==='on',
        scheduleLocationId:String(values.get('scheduleLocationId')||'')||null
    };
    if(!model.pools.some(pool=>pool.location===employee.location&&pool.role===employee.role))throw Error('Create a matching Location Roles pool before assigning this employee to that location and role.');
    if(employee.scheduleLocationId&&!scheduleLocations.some(location=>location.id===employee.scheduleLocationId&&location.location===employee.location&&roleFitsScheduleGroup(employee.role,location)))throw Error('The schedule location must match the employee’s location and role group.');
    let rosterEntry=model.roster.find(entry=>String(entry.id)===String(originalId||id));
    let profileChanged=!!rosterEntry&&(rosterEntry.location!==employee.location||rosterEntry.role!==employee.role);
    if(employee.active&&profileChanged)throw Error('Make the employee inactive before changing their location or role. Complete the updated roster profile before reactivating them.');
    if(employee.active&&!rosterEntry)throw Error('Add this employee to Roster settings before activating them.');
    if(employee.active&&rosterEntry?.active===false&&!employeeProfileReady(rosterEntry))throw Error('Complete the employee’s Roster settings before making them active.');
    let response=await directoryRequest(registered?'/employees/'+encodeURIComponent(originalId):'/employees',{
        method:registered?'PUT':'POST',body:JSON.stringify(employee)
    });
    employee={...employee,...response.employee};
    if(rosterEntry&&profileChanged){
        let index=model.roster.indexOf(rosterEntry);
        model.roster[index]=blankRosterProfile(employee,index)
    }
    else if(rosterEntry){
        rosterEntry.id=employee.id;
        rosterEntry.name=employee.name;
        rosterEntry.location=employee.location;
        rosterEntry.role=employee.role;
        rosterEntry.bamboohrId=employee.bamboohrId;
        rosterEntry.scheduleLocationId=employee.scheduleLocationId;
        rosterEntry.active=employee.active;
        rosterEntry.sourceType=employee.source
    }
    else model.roster.push(blankRosterProfile(employee,model.roster.length));
    model.roster.forEach((entry,index)=>entry.index=index);
    await loadDirectoryData();
    await saveState();
    $('employeeDialog').close();
    if(page==='employees')render(true);
    else render();
    message('Employee record saved.')
}
async function saveScheduleLocationForm(locationId){
    let form=$('scheduleLocationForm'),values=new FormData(form),data={
        name:String(values.get('name')).trim(),bambooScheduleId:String(values.get('bambooScheduleId')).trim(),
        location:String(values.get('location')),roleGroup:String(values.get('roleGroup')||'').trim(),
        managerName:String(values.get('managerName')).trim(),managerEmail:String(values.get('managerEmail')).trim()
    };
    let assigned=employeeDirectory.filter(employee=>employee.scheduleLocationId===locationId);
    if(assigned.some(employee=>!model.pools.some(pool=>pool.location===data.location&&pool.role===employee.role)))throw Error('Create matching Location Roles pools for all assigned employee roles before changing this schedule location.');
    await directoryRequest(locationId?'/schedule-locations/'+encodeURIComponent(locationId):'/schedule-locations',{
        method:locationId?'PUT':'POST',body:JSON.stringify(data)
    });
    await loadDirectoryData();
    await saveState();
    $('scheduleLocationDialog').close();
    render(true);
    message('Schedule location saved.')
}
async function saveEmployeeAssignments(){
    if(model.locked)throw Error('Unlock settings in Controls before reassigning employees.');
    await directoryRequest('/schedule-locations/'+encodeURIComponent(assignLocationId)+'/employees',{
        method:'PUT',body:JSON.stringify({employeeIds:[...assignEmployeeIds]})
    });
    await loadDirectoryData();
    await saveState();
    $('assignEmployeesDialog').close();
    render(true);
    message('Employee assignments saved.')
}
function openAssignmentDialog(locationId){
    let target=scheduleLocations.find(location=>location.id===locationId);
    if(!target)throw Error('The selected schedule location could not be found.');
    assignLocationId=locationId;
    assignEmployeeIds=new Set(employeeDirectory.filter(employee=>employee.active&&employee.scheduleLocationId===locationId).map(employee=>employee.id));
    assignCandidateIds=new Set();
    renderAssignmentDialog();
    $('assignEmployeesDialog').showModal()
}
const CONTROL_FIELDS=[['shifts','Shifts per employee',1,7,1],['hours','Paid hours per shift',.5,24,.5],['span','Elapsed shift span · hours',.5,24,.5],['rest','Minimum rest hours',0,48,.5],['preference','Preference weight',0,1e6,1],['proximity','Proximity weight',0,1e6,1],['random','Random factor weight',0,1e6,1],['bonus','Attendance priority bonus',0,1e7,1]];
function selectedPool(){
    return model.pools.find(p=>p.id===(previewId||key(model.controls.location,model.controls.role)))||model.pools[0]||null
}
function controls(){
    let c=model.controls,p=selectedPool();
    if(!p)return heading('ENGINE / CONTROLS','One locked snapshot. Many weeks.','Create or accept a location and add at least one role in Location Roles before configuring schedules.')+panel('No location-role pools','<p>Schedule controls become available after a location-role pool is created.</p><button type="button" data-page="pools">Open Location Roles</button>');
    let rs=poolRoster(model,p),l=model.locations.find(x=>x.name===p.location);
    let starts=poolStarts(p),can=p.shares.every(isNum)&&l&&l.intensity.every(isNum)&&sum(l.intensity.map((x,i)=>l.open[i]?x:0))>0,dem=can?splitDemand(rs.length,p.shares,c,l,starts):null;
    return heading('ENGINE / CONTROLS','One locked snapshot. Many weeks.','The first week starts on the selected Monday. Generation advances it by seven days and selects Location and Role automatically for each enabled pool.')+panel('Generation controls',`<div class="formgrid"><label>Week commencing · Monday<input type="date" value="${esc(c.week)}" data-control="week" ${disabled()}></label><label>Weeks · all enabled location × roles<input type="number" min="1" max="52" step="1" value="${scheduleWeeks(model)}" data-control="weeks" ${disabled()}></label>${CONTROL_FIELDS.map(([k,t,min,max,step])=>`<label>${t}<input type="number" min="${min}" max="${max}" step="${step}" value="${c[k]}" data-control="${k}" ${disabled()}></label>`).join('')}<label>Attendance priority ${select([[1,'Enabled · top 3 by pool'],[0,'Disabled']],c.attendanceEnabled,`data-control="attendanceEnabled" ${disabled()}`)}</label><label>Make-up pass ${select([[1,'Enabled'],[0,'Disabled']],c.makeup,`data-control="makeup" ${disabled()}`)}</label></div><div class="callout">Paid hours feed weekly hours. Elapsed shift span feeds displayed end times and rest checks; end times are calculated from each start and this setting.</div>`)+panel('Resolved Controls preview',`<div class="toolbar"><label>Preview location / role ${select(model.pools.map(x=>[x.id,x.location+' · '+x.role]),p.id,'id="previewPool"')}</label><span>Control Location: ${esc(p.location)} · Role: ${esc(p.role)} · HC: ${rs.length}</span></div>${dem?`<div class="tablewrap"><table><thead><tr><th>Day</th><th>Open</th><th>Daily total</th>${starts.map(s=>'<th>'+timeLabel(s)+'</th>').join('')}</tr></thead><tbody>${dem.map((r,i)=>`<tr><td>${DAYS[i]}</td><td>${l.open[i]}</td><td>${sum(r)}</td>${r.map(x=>'<td>'+x+'</td>').join('')}</tr>`).join('')}</tbody></table></div>`:'<p>Supply valid shift shares and META intensities to see demand.</p>'}`)+errorsPanel()+panel('Lock configuration',`<p>Locking fixes the roster, operating patterns, controls and enabled pool settings for generation. Unlocking creates a new revision; earlier saved schedules retain their own configuration snapshots.</p><div class="actions"><button type="button" class="primary" data-action="${model.locked?'unlock':'lock'}">${model.locked?'Unlock & revise settings':'Validate & lock settings'}</button><button type="button" data-action="generate" ${model.locked?'':'disabled'}>Generate schedules</button></div>`)
}
function metaPage(){
    const remoteNames=new Set(sharedMeta?.locations?.map(location=>location.name.toLowerCase())||[]);
    const missing=model.locations.filter(location=>!remoteNames.has(location.name.toLowerCase()));
    const unused=sharedMeta?.configured?sharedMeta.locations.filter(location=>!model.locations.some(item=>item.name.toLowerCase()===location.name.toLowerCase())).length:0;
    const metaPanel=sharedMetaError
        ?panel('Shared META unavailable',`<p class="badtext">${esc(sharedMetaError)}</p><button type="button" data-action="reloadSharedMeta">Retry</button>`)
        :!model.locations.length
            ?panel('No locations',`<p>Location calendars will appear after locations are imported, added, or accepted from BambooHR.</p><button type="button" data-page="pools">Open Location Roles</button>`)
        :!sharedMeta?.configured
            ?panel('Shared META setup',`<p>Manager location settings are stored centrally. Preview and explicitly import the current browser META settings once before managers can use them.</p><button type="button" class="primary" data-action="initializeSharedMeta">Preview and initialize shared META</button>`)
            :panel('Shared META',`<p>Shared settings are active · revision ${sharedMeta.revision} · ${sharedMeta.locations.length} physical locations.${sharedMeta.locked?' Configuration is locked and read-only.':''}</p>${missing.length?`<p class="note">${missing.length} workspace location(s) are not shared yet. Existing server values will be retained.</p><button type="button" data-action="syncSharedMetaLocations" ${sharedMeta.locked?'disabled':''}>Preview and add locations</button>`:''}${unused?`<p class="note">${unused} server location(s) are not in this browser workspace; their saved values have been retained.</p>`:''}`);
    const table=model.locations.length?`<div class="tablewrap"><table class="metagrid"><thead><tr><th>Location</th>${DAYS.map(d=>'<th>'+d+' intensity % / open</th>').join('')}<th>Total intensity</th></tr></thead><tbody>${model.locations.map((l,i)=>`<tr><td>${esc(l.name)}</td>${DAYS.map((d,j)=>`<td><input type="number" min="0" max="100" step="any" value="${percent(l.intensity[j])}" data-meta="${i}" data-day="${j}" data-field="intensity" ${disabled()} aria-label="${esc(l.name+' '+d)} intensity"><label class="check"><input type="checkbox" data-meta="${i}" data-day="${j}" data-field="open" ${l.open[j]===1?'checked':''} ${disabled()}> Open</label></td>`).join('')}<td>${f(sum(l.intensity.map(x=>x||0))*100,2)}%</td></tr>`).join('')}</tbody></table></div>`:'<p>No location calendars have been added.</p>';
    return heading('OPERATIONS / META','Define how each location works.','Daily intensities are normalized across open days. A closed day receives no demand or make-up shifts.')+metaPanel+panel('Location calendars & workload intensity',table,'Set all seven values for any enabled location. For closed days you may explicitly enter 0.')+errorsPanel()
}
function scheduleViewWithoutAcceptedHistory(){
    let all=model.results,visible=visibleScheduleRuns(),selected=visible.find(r=>r.id===model.selectedRun)||visible[0];
    if(selected)model.selectedRun=selected.id;
    return heading('OUTPUT / WEEKLY SCHEDULE','Every week, saved by pool.','Review demand coverage, supplemental shifts and employee target shortfalls. Schedule times use the elapsed span configured for that run. Every generation uses fresh randomness. Refresh & shuffle all processes every saved schedule, including earlier revisions and pools outside the current horizon, using each schedule’s saved constraints.')+`<div class="toolbar"><button type="button" class="primary" data-action="generate" ${model.locked?'':'disabled'}>${all.length?'Generate / update selected horizon':'Generate schedules'}</button><button type="button" data-action="refresh" ${model.locked&&all.length?'':'disabled'}>↻ Refresh & shuffle all</button>${model.previousScheduleSet?'<button type="button" data-action="undoShuffle">Undo last shuffle</button>':''}<button type="button" data-action="timeOffs">View time-offs</button><button type="button" data-action="timeOffWorkbook">Upload time-offs · XLSX</button>${membershipFeatureEnabled('shiftTrades')?`<button type="button" data-action="trade" ${all.length?'':'disabled'}>Trade shifts</button>`:''}<button type="button" data-action="scheduleUpload">Upload schedules · XLSX</button><button type="button" data-action="scheduleTemplate">Download schedule template</button><button type="button" data-action="downloadVisible" ${visible.length?'':'disabled'}>Download filtered schedules · XLSX</button><button type="button" data-action="download" ${all.length?'':'disabled'}>Download all schedules · XLSX</button><button type="button" data-action="email" ${all.length?'':'disabled'}>Email schedules</button><button type="button" data-action="csv" ${all.length?'':'disabled'}>Combined CSV</button></div>`+scheduleFilters()+(!all.length?panel('No saved schedules',model.locked?'<p>Generate schedules from the locked configuration.</p>':'<p>Complete the settings and lock them in Controls before generating the first schedule.</p>'):`<div class="toolbar"><label>Saved week & pool ${select(visible.map(r=>[r.id,r.start+' to '+r.end+' · '+r.location+' · '+r.role+' · rev '+r.revision]),selected?.id,'id="runSelect"')}</label></div>`+(selected?runView(selected):panel('No matching schedules','<p>Change the filters to view saved schedules.</p>'))+savedScheduleRegister(visible))
}
function savedScheduleRegister(visible){
    return panel('Saved schedule register',`<p class="note">Delete removes only the browser-saved workspace copy. Accepted schedules and BambooHR shifts are retained.</p><div id="savedScheduleRegister" class="tablewrap schedule-register" tabindex="0" role="region" aria-label="Saved schedule register"><table><thead><tr><th>Week period</th><th>Location / role</th><th>Revision</th><th>Demand filled</th><th>Make-up</th><th>Unfilled demand</th><th>Employee shortfall</th><th>Actions</th></tr></thead><tbody>${visible.map(r=>`<tr><td><button type="button" data-run="${esc(r.id)}">${esc(r.start)} → ${esc(r.end)}</button></td><td>${esc(r.location)}<small>${esc(r.role)}</small></td><td>${r.revision}</td><td>${r.primary}</td><td>${r.makeup}</td><td>${r.uncovered.length}</td><td>${sum(r.shortages.map(x=>x.missing))}</td><td><div class="actions employee-actions attendance-actions"><button type="button" class="danger" data-action="deleteSavedSchedule" data-id="${esc(r.id)}" ${tenantAuthTenantId?'':'disabled'} aria-label="Delete saved schedule ${esc(r.start+' '+r.location+' '+r.role)}">Delete</button></div></td></tr>`).join('')}</tbody></table></div>`)
}
function runView(r){
    if(!r)return '';
    let c=r.controls;
    return (r.importWarnings?.length?panel('Uploaded schedule · missing profile information','<ul>'+r.importWarnings.map(w=>'<li>'+esc(w)+'</li>').join('')+'</ul>'):'')+overtimePanel(r)+stats([['Week period',r.start,'Through '+r.end],['Primary shifts filled',r.primary,f(sum(r.requirements.flat()))+' demand slots'],['Make-up shifts',r.makeup,'Shown with a + marker'],['Review items',r.uncovered.length+r.shortages.length,'Unfilled demand slots + employees below target']])+panel(esc(r.location+' · '+r.role),`<div class="actions">${badge('Revision '+r.revision)} ${r.timeOffCheck?badge(r.timeOffCheck.status==='success'?(r.timeOffCheck.source==='workbook'?'Workbook time-offs applied':'BambooHR time-offs checked'):r.timeOffCheck.status==='error'?'Time-offs not checked · API error':'Time-offs not configured',r.timeOffCheck.status==='error'?'warn':''):''} ${r.controls.shuffle?badge('Shuffled · seed '+r.controls.seed):''} ${badge(r.uncovered.length||r.shortages.length?'Review required':'Targets met',r.uncovered.length||r.shortages.length?'warn':'good')}<span class="note">${r.imported?'Uploaded schedule · '+esc(r.sourceName):r.revision!==model.revision?'Earlier configuration revision · included in shuffle all':'Current configuration revision'}</span></div><div class="tablewrap schedule"><table><thead><tr><th>Employee / ID</th>${DAYS.map((d,i)=>`<th>${d}<small>${addDays(r.start,i)}</small></th>`).join('')}<th>Shifts / hours</th><th>Missing</th></tr></thead><tbody>${r.employees.map(e=>`<tr><td class="sticky">${esc(e.name)}<small>${esc(e.id)}</small></td>${e.slots.map((s,d)=>`<td class="${s===null?(e.timeOff?.[d]?'leave':'off'):e.types[d]==='Make-up'?'added':'duty'}">${s===null?(e.timeOff?.[d]?'time-off':'OFF'):esc(shiftLabel(s,c.span))+(e.types[d]==='Make-up'?'<b class="plus"> +</b>':'')}</td>`).join('')}<td>${e.slots.filter(x=>x!==null).length} / ${f(e.slots.filter(x=>x!==null).length*c.hours,1)}h</td><td>${Math.max(0,c.shifts-e.slots.filter(x=>x!==null).length)}</td></tr>`).join('')}</tbody></table></div>`,'+ = supplemental make-up shift; these do not erase unfilled primary demand. time-off marks approved BambooHR absence (or uploaded time-off); OFF means no assignment. Overnight shifts that overlap the next day’s time-off are also excluded.')+(membershipFeatureEnabled('shiftTrades')&&r.tradeHistory?.length?panel('Confirmed shift trades','<ul>'+r.tradeHistory.map(t=>'<li>'+esc(t.firstName)+' ↔ '+esc(t.secondName)+' · '+esc(t.days.map(d=>DAYS[d]).join(', '))+' · '+esc(t.at)+'</li>').join('')+'</ul>'):'')+panel('Demand coverage · assigned / required',`<div class="tablewrap"><table><thead><tr><th>Day</th>${STARTS.map(s=>'<th>'+timeLabel(s)+'</th>').join('')}<th>Make-up total</th></tr></thead><tbody>${r.requirements.map((rq,d)=>`<tr><td>${DAYS[d]}</td>${rq.map((need,j)=>{
        let got=r.employees.filter(e=>e.slots[d]===STARTS[j]&&e.types[d]==='Demand').length;return `<td class="${got<need?'gap':''}">${got} / ${need}</td>`
    }
    ).join('')}<td>${r.employees.filter(e=>e.types[d]==='Make-up').length}</td></tr>`).join('')}</tbody></table></div>`)+(r.shortages.length?panel('Employee target shortfalls','<ul>'+r.shortages.map(e=>'<li>'+esc(e.name)+' · '+e.missing+' missing shifts</li>').join('')+'</ul>'):'')
}
let acceptedSchedules=[],acceptedScheduleError='';
async function acceptedScheduleRequest(path='',options={}){
    let response=await fetch('/api/accepted-shifts'+path,{
        ...options,headers:{
            'Content-Type':'application/json',...(options.headers||{})
        }
    }),body=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(body.error||'Accepted schedule request failed with HTTP '+response.status+'.');
    return body
}
async function loadAcceptedSchedules(){
    try{
        let result=await acceptedScheduleRequest();
        acceptedSchedules=result.schedules;
        let updated=false;
        for(let record of acceptedSchedules){
            let index=model?.results?.findIndex(run=>run.id===record.id);
            if(index===undefined||index<0)continue;
            let existing=model.results[index],known=new Set((existing.tradeHistory||[]).map(trade=>trade.tradeId));
            if((record.schedule.tradeHistory||[]).some(trade=>trade.tradeId&&!known.has(trade.tradeId))){
                model.results[index]=clone(record.schedule);
                rebuildScheduleAudit(model.results[index]);
                updated=true
            }
        }
        if(updated)await saveState();
        acceptedScheduleError=''
    }
    catch(error){
        acceptedScheduleError=error.message
    }
}
function acceptedHistoryPanel(){
    if(!membershipFeatureEnabled('scheduleHistory'))return panel('Previously accepted shifts','<p>Schedule history is included with Silver and above. Accepted schedules remain available for BambooHR publishing.</p>');
    if(acceptedScheduleError)return panel('Previously accepted shifts',`<p class="badtext">${esc(acceptedScheduleError)}</p>`);
    if(!acceptedSchedules.length)return panel('Previously accepted shifts','<p>No schedules have been accepted yet. Accept a generated or uploaded schedule to save it to the app database.</p>');
    return panel('Previously accepted shifts',acceptedSchedules.map(record=>{
        let r=record.schedule;
        return `<details class="accepted-schedule"><summary>${esc(r.start)} · ${esc(r.location)} · ${esc(r.role)} · accepted ${esc(record.acceptedAt)}</summary><div class="actions"><button type="button" class="danger" data-action="undoAccept" data-run-id="${esc(r.id)}">Undo accept</button><span class="note">Removes only the accepted database copy; generated schedules remain unchanged.</span></div><div class="tablewrap schedule"><table><thead><tr><th>Employee / ID</th>${DAYS.map((day,index)=>`<th>${day}<small>${addDays(r.start,index)}</small></th>`).join('')}</tr></thead><tbody>${r.employees.map(employee=>`<tr><td class="sticky">${esc(employee.name)}<small>${esc(employee.id)}</small></td>${employee.slots.map((start,day)=>`<td>${start===null?'OFF':esc(shiftLabel(start,r.controls.span))}${employee.types[day]==='Make-up'?'<b class="plus"> +</b>':''}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`
    }).join(''))
}
function acceptedPublishGroups(){
    let groups=new Map();
    for(let record of acceptedSchedules){
        let run=record.schedule,key=JSON.stringify([run.start,run.location,run.role]),group=groups.get(key);
        if(!group){
            group={start:run.start,location:run.location,role:run.role,records:[]};
            groups.set(key,group)
        }
        group.records.push(record)
    }
    return [...groups.values()]
}
function assignedPublishSelections(record){
    let run=record.schedule,starts=run.shiftStarts||STARTS,selections=[];
    for(let day=0;day<DAYS.length;day++)for(let start of starts){
        if(run.employees.some(employee=>employee.slots[day]===start)){
            selections.push({runId:run.id,day,start})
        }
    }
    return selections
}
function bambooPublishPage(){
    let selectedKeys=new Set(publishSelection.map(item=>JSON.stringify([item.runId,item.day,item.start])));
    let records=acceptedPublishGroups().map((group,groupIndex)=>{
        let groupSelections=group.records.flatMap(assignedPublishSelections);
        let allSelected=groupSelections.length>0&&groupSelections.every(item=>selectedKeys.has(JSON.stringify([item.runId,item.day,item.start])));
        let scheduleTables=group.records.map(record=>{
            let run=record.schedule,starts=run.shiftStarts||STARTS;
            return `<section class="publish-record"><h4>Accepted ${esc(record.acceptedAt)}</h4><div class="tablewrap"><table><thead><tr><th>Day</th>${starts.map(start=>'<th>'+shiftLabel(start,run.controls.span)+'</th>').join('')}</tr></thead><tbody>${DAYS.map((day,index)=>{
                let countAt=start=>run.employees.filter(employee=>employee.slots[index]===start).length;
                return `<tr><td>${day}<small>${addDays(run.start,index)}</small></td>${starts.map(start=>{
                    let count=countAt(start),selected=selectedKeys.has(JSON.stringify([run.id,index,start]));
                    return `<td>${count?`<label class="check"><input type="checkbox" data-publish-run="${esc(run.id)}" data-publish-day="${index}" data-publish-start="${start}" ${selected?'checked':''}> ${count} assigned</label>`:`${count} assigned`}</td>`
                }).join('')}</tr>`
            }).join('')}</tbody></table></div></section>`
        }).join('');
        return `<details class="accepted-schedule" data-publish-group="${groupIndex}"><summary>${esc(group.start)} · ${esc(group.location)} · ${esc(group.role)}${group.records.length>1?` · ${group.records.length} accepted schedules`:''}</summary><div class="actions"><label class="check"><input type="checkbox" data-publish-group-all="${groupIndex}" ${allSelected?'checked':''} ${groupSelections.length?'':'disabled'}> Select all assigned shifts for this location · role · period</label><span>${groupSelections.length} assigned shifts</span></div>${scheduleTables}</details>`
    }).join('');
    let selectionCount=publishSelection.length;
    return heading('OUTPUT / BAMBOOHR','Publish accepted shifts only.','Select shifts from previously accepted schedules, preview the exact BambooHR schedule payloads, then confirm before posting. The API key remains on the Flask server.')+
        panel('BambooHR connection',(publishError?`<p class="badtext">${esc(publishError)}</p>`:publishConfigured?'<p>Server credential is configured. No credential is sent to the browser.</p>':'<p class="badtext">The BambooHR API key is not configured for this business. Add it in Settings before publishing.</p>')+'<button type="button" data-action="refreshBambooStatus">Refresh server status</button>')+
        (acceptedScheduleError?panel('Accepted schedules unavailable',`<p class="badtext">${esc(acceptedScheduleError)}</p>`):'')+
        (acceptedSchedules.length?panel('Select accepted shifts',records+`<div class="actions"><span>${selectionCount} shifts selected (maximum 500 per publish)</span><button type="button" data-action="previewPublish" class="primary" ${selectionCount?'':'disabled'}>Preview BambooHR changes</button><button type="button" data-action="clearPublishSelection" ${selectionCount?'':'disabled'}>Clear selection</button></div><p class="note">Shift start and end times use the accepted schedule's saved duration and Jamaica timezone. Employee BambooHR IDs and schedule mappings are validated by the server before preview.</p>`):panel('Select accepted shifts','<p>No accepted schedules are available. Accept a generated or uploaded schedule first.'))
        +(publishPreview?panel('Preview · no changes posted',`<div class="tablewrap"><table><thead><tr><th>Schedule</th><th>UTC start</th><th>UTC end</th><th>Employees</th><th>BambooHR IDs</th></tr></thead><tbody>${publishPreview.map(item=>`<tr><td>${esc(item.scheduleName)}</td><td>${esc(item.start)}</td><td>${esc(item.end)}</td><td>${esc(item.employeeNames.join(', '))}</td><td>${esc(item.employeeIds.join(', '))}</td></tr>`).join('')}</tbody></table></div><div class="actions"><button type="button" class="primary" data-action="openPublishConfirm" ${publishConfigured?'':'disabled'}>Continue to publish confirmation</button></div>`):'')+
        (publishResults.length?panel('Publishing results',`<div class="tablewrap"><table><thead><tr><th>Schedule</th><th>Start</th><th>Result</th><th>Details</th></tr></thead><tbody>${publishResults.map(result=>`<tr><td>${esc(result.scheduleName)}</td><td>${esc(result.start)}</td><td>${badge(result.success?'Posted':'Failed',result.success?'good':'bad')}</td><td>${esc(result.error||('HTTP '+result.status))}</td></tr>`).join('')}</tbody></table></div>`):'')
}
function runView(r){
    if(!r)return '';
    let c=r.controls,starts=r.shiftStarts||STARTS,record=acceptedSchedules.find(item=>item.id===r.id);
    let dayCell=(employee,day)=>{
        let options=[['off','OFF'],...starts.map(start=>[String(start),shiftLabel(start,c.span)])];
        return `<td class="${employee.slots[day]===null?(employee.timeOff?.[day]?'leave':'off'):employee.types[day]==='Make-up'?'added':'duty'}"><select aria-label="${esc(employee.name+' '+DAYS[day]+' shift')}" data-schedule-shift="true" data-run-id="${esc(r.id)}" data-employee-id="${esc(employee.id)}" data-day="${day}">${options.map(([value,label])=>{
            let start=value==='off'?null:Number(value),selected=employee.slots[day]===null?value==='off':employee.slots[day]===start;
            return `<option value="${value}" ${selected?'selected':''} ${start!==null&&!employeeCanStart(employee,start)&&!selected?'disabled':''}>${esc(label)}</option>`
        }).join('')}</select>${employee.types[day]==='Make-up'?'<b class="plus"> +</b>':''}</td>`
    };
    return (r.importWarnings?.length?panel('Uploaded schedule · missing profile information','<ul>'+r.importWarnings.map(w=>'<li>'+esc(w)+'</li>').join('')+'</ul>'):'')+overtimePanel(r)+stats([['Week period',r.start,'Through '+r.end],['Primary shifts filled',r.primary,f(sum(r.requirements.flat()))+' demand slots'],['Make-up shifts',r.makeup,'Shown with a + marker'],['Review items',r.uncovered.length+r.shortages.length,'Unfilled demand slots + employees below target']])+panel(esc(r.location+' · '+r.role),`<div class="actions">${badge('Revision '+r.revision)} ${r.imported?badge('Uploaded schedule'):badge('Generated schedule')} ${record?badge('Accepted','good'):badge('Not accepted','warn')}<button type="button" class="primary" data-action="acceptSchedule" data-run-id="${esc(r.id)}">${record?'Update accepted copy':'Accept this schedule'}</button><span class="note">${r.imported?'Uploaded · '+esc(r.sourceName):r.revision!==model.revision?'Earlier configuration revision':'Current configuration revision'}</span></div><div class="tablewrap schedule"><table><thead><tr><th>Employee / ID</th>${DAYS.map((day,index)=>`<th>${day}<small>${addDays(r.start,index)}</small></th>`).join('')}<th>Shifts / hours</th><th>Missing</th></tr></thead><tbody>${r.employees.map(employee=>`<tr><td class="sticky">${esc(employee.name)}<small>${esc(employee.id)}</small></td>${employee.slots.map((_,day)=>dayCell(employee,day)).join('')}<td>${employee.slots.filter(start=>start!==null).length} / ${f(employee.slots.filter(start=>start!==null).length*c.hours,1)}h</td><td>${Math.max(0,c.shifts-employee.slots.filter(start=>start!==null).length)}</td></tr>`).join('')}</tbody></table></div>`,'Click a shift cell to select OFF or a start configured for this pool. Shift end times follow the run’s elapsed shift span. A shift that is not enabled for that employee is unavailable in the selector.')+panel('Demand coverage · assigned / required',`<div class="tablewrap"><table><thead><tr><th>Day</th>${starts.map(start=>'<th>'+timeLabel(start)+'</th>').join('')}<th>Make-up total</th></tr></thead><tbody>${r.requirements.map((requirement,day)=>`<tr><td>${DAYS[day]}</td>${requirement.map((need,index)=>{
        let start=starts[index],assigned=r.employees.filter(employee=>employee.slots[day]===start&&employee.types[day]==='Demand').length;
        return `<td class="${assigned<need?'gap':''}">${assigned} / ${need}</td>`
    }).join('')}<td>${r.employees.filter(employee=>employee.types[day]==='Make-up').length}</td></tr>`).join('')}</tbody></table></div>`)+(r.shortages.length?panel('Employee target shortfalls','<ul>'+r.shortages.map(employee=>'<li>'+esc(employee.name)+' · '+employee.missing+' missing shifts</li>').join('')+'</ul>'):'')+(membershipFeatureEnabled('shiftTrades')&&r.tradeHistory?.length?panel('Confirmed shift trades','<ul>'+r.tradeHistory.map(trade=>'<li>'+esc(trade.firstName)+' ↔ '+esc(trade.secondName)+' · '+esc(trade.days.map(day=>DAYS[day]).join(', '))+' · '+esc(trade.at)+'</li>').join('')+'</ul>'):'')
}
function schedules(){
    return scheduleViewWithoutAcceptedHistory()+acceptedHistoryPanel()
}
function sourcePage(){
    return heading('DATA / SOURCE & SAVING','Your workbook, your scheduling inputs.','Upload a pre-filled version of the same model to replace the configuration basis. Saved schedules retain their source settings.')+panel('Source workbook',`<p><b>${esc(model.sourceName)}</b><br><span class="note">Imported ${esc(model.sourceImported)}</span></p><div class="actions"><button type="button" class="import" data-action="sourcePicker">Upload updated source</button><button type="button" data-action="backup">Download workspace backup</button><button type="button" data-action="restore">Restore backup</button><button type="button" data-action="sourceInputs">Download configured inputs · XLSX</button></div><p class="note">Import replaces the editable source configuration and unlocks settings. Previously generated schedules retain their configuration snapshots and revision. Refresh & shuffle all can change their allocations using those saved constraints.</p>`)+panel('What is saved',storageMode==='session'?'<p>This context blocks IndexedDB. Your source inputs, settings, lock state and schedule snapshots remain available for the current session. Download the portable ZIP bundle when hosted or download a workspace backup to retain them after refresh or closing. Excel and CSV exports contain schedule output; use JSON backup or portable ZIP bundle to preserve the full workspace.</p>':'<p>The source inputs, settings, lock state and weekly schedule snapshots are saved in this browser using IndexedDB. Download a workspace backup or portable ZIP bundle for a durable copy. Browser storage is not shared with other team members and may be cleared by browser policies.</p>')+panel('Engine interpretation','<ul><li>Location Roles rows 7–46 define available source pools. Headcount is recomputed from the roster, capped at 21 per enabled pool.</li><li>Controls Location and Role are resolved for each generated pool; the date is incremented weekly. A Controls snapshot is saved for every result.</li><li>Daily demand uses cumulative rounding of headcount × weekly shift target, weighted across open-day intensity. Shift demand uses largest-remainder rounding with deterministic shift-order ties, so totals reconcile.</li><li>Primary scoring: remaining weekly shifts × 10,000; fixed-flexibility priority +1,000; preference and proximity weights, a fresh random 1–3 rotation factor per employee/week multiplied by the random weight, and optional top-three attendance preference bonus. A fresh seed also randomizes equal-priority demand ordering and allocation ties.</li><li>Make-up shifts use preference/scoring, then lowest daily staffing, with randomized ties. All four shifts are supported. Added shifts are audited separately.</li><li>Rest uses elapsed shift span and actual time between assigned intervals, including across generated weeks. Explicit shift permissions also apply to fixed-preference employees.</li><li>This browser model corrects stale three-shift references and repeated/no-op dependencies in the uploaded formulas. It does not execute arbitrary Excel formulas. New layouts or formula-rule changes require an app update.</li><li>The original model contains missing roster fields and workload shares. These remain visible and block generation only when their pools are enabled. Attendance blanks receive no bonus.</li></ul>')
}
function render(preserveScroll=false){
    if(!model)return;
    applyBranding();
    let scrollPosition=preserveScroll?{x:window.scrollX,y:window.scrollY,wrappers:[...document.querySelectorAll('#content .tablewrap')].map(wrapper=>({left:wrapper.scrollLeft,top:wrapper.scrollTop}))}:null;
    let openPublishGroups=new Set([...document.querySelectorAll('#content details[data-publish-group][open]')].map(details=>details.dataset.publishGroup));
    profileHeader();
    applyMenuSettings();
    document.documentElement.dataset.theme=model.theme;
    try{localStorage.setItem('cbl-application-theme',model.theme);}
    catch(error){console.warn('Unable to remember application theme:',error);}
    $('sourceName').textContent=model.sourceName;
    $('lockState').textContent=model.locked?'● Locked · rev '+model.revision:'○ Editable · rev '+model.revision;
    $('lockState').className=model.locked?'lock locked':'lock';
    storageStatus();
    $('content').innerHTML=({
        home,pools,roster,employees:employeesPage,scheduleLocations:scheduleLocationsPage,attendance:attendancePage,controls,meta:metaPage,schedules,publish:bambooPublishPage,source:sourcePage,settings:settingsPage,links:workforceLinksPage
    }
    [page])();
    document.querySelectorAll('#content [data-action="timeOffWorkbook"]').forEach(button=>{
        button.remove()
    });
    if(page==='schedules'){
        let selected=model.results.find(run=>run.id===model.selectedRun);
        if(selected?.timeOffCheck?.status==='error'){
            let warning=document.createElement('div');
            warning.className='callout';
            warning.setAttribute('role','alert');
            warning.textContent='BambooHR time-off data unavailable; review this schedule. '+selected.timeOffCheck.error;
            $('content').prepend(warning)
        }
        document.querySelectorAll('#content details.accepted-schedule').forEach((details,index)=>{
            let check=acceptedSchedules[index]?.schedule?.timeOffCheck;
            if(check?.status!=='error')return;
            let warning=document.createElement('p');
            warning.className='badtext';
            warning.setAttribute('role','alert');
            warning.textContent='BambooHR time-off data unavailable when accepted; review this schedule. '+check.error;
            details.querySelector('summary')?.after(warning)
        })
    }
    document.querySelectorAll('#content details[data-publish-group]').forEach(details=>{
        details.open=openPublishGroups.has(details.dataset.publishGroup)
    });
    if(scrollPosition)requestAnimationFrame(()=>{
        window.scrollTo(scrollPosition.x,scrollPosition.y);
        document.querySelectorAll('#content .tablewrap').forEach((wrapper,index)=>{
            let saved=scrollPosition.wrappers[index];
            if(saved)wrapper.scrollTo(saved.left,saved.top)
        })
    });
    applyMenuSettings();
    bindScheduleFilters();
    sizeScheduleRegister();
    document.querySelectorAll('[data-page]').forEach(e=>e.classList.toggle('active',e.dataset.page===page));
    $('poolLocation')?.addEventListener('change',e=>{
        filterLoc=e.target.value;render()
    }
    );
    $('rosterLocation')?.addEventListener('change',e=>{
        filterLoc=e.target.value;render()
    }
    );
    $('rosterRole')?.addEventListener('change',e=>{
        filterRole=e.target.value;render()
    }
    );
    $('employeeLocationFilter')?.addEventListener('change',e=>{
        employeeLocationFilter=e.target.value;render()
    }
    );
    $('employeeRoleFilter')?.addEventListener('change',e=>{
        employeeRoleFilter=e.target.value;render()
    }
    );
    $('rosterSearch')?.addEventListener('change',e=>{
        search=e.target.value;render()
    }
    );
    $('previewPool')?.addEventListener('change',e=>{
        previewId=e.target.value;render()
    }
    );
    $('runSelect')?.addEventListener('change',e=>{
        model.selectedRun=e.target.value;render()
    }
    )
}
let saveTimer;
function queueSave(){
    clearTimeout(saveTimer);
    saveTimer=setTimeout(()=>saveState().catch(e=>message('Changes are not saved in this browser: '+e.message+'. Download a backup.',true)),200)
}
function refreshConfigurationIndicators(){
    if(page==='pools'){
        for(let row of document.querySelectorAll('#content [data-pool-row]')){
            let pool=model.pools[Number(row.dataset.poolRow)],statusCell=row.lastElementChild;
            if(!pool||!statusCell)continue;
            let status=poolState(pool);
            statusCell.title=status.issues.join('; ');
            statusCell.innerHTML=badge(status.count===0?'No roster':status.ready?'Ready':'Incomplete',status.ready?'good':'warn')
        }
    }
    let current=document.querySelector('#content .validation');
    if(current){
        let detailsOpen=current.querySelector('details')?.open??false,template=document.createElement('template');
        template.innerHTML=errorsPanel();
        let replacement=template.content.firstElementChild;
        if(replacement.querySelector('details'))replacement.querySelector('details').open=detailsOpen;
        current.replaceWith(replacement)
    }
}
async function updateMetaSetting(element){
    const workspace=model,index=Number(element.dataset.meta),day=Number(element.dataset.day),field=element.dataset.field;
    const value=field==='open'?(element.checked?1:0):element.value===''?null:Number(element.value)/100;
    try{
        if(!Number.isInteger(index)||!workspace.locations[index]||!Number.isInteger(day)||day<0||day>6||
            !['open','intensity'].includes(field)||(field==='intensity'&&value!==null&&(!Number.isFinite(value)||value<0||value>1))){
            throw Error('Choose a valid location, day and intensity.');
        }
        await authorizeDataSettings('meta-update');
        if(model!==workspace)throw Error('The workspace changed. Reload META before editing.');
        if(model.locked||sharedMeta?.locked)throw Error('Unlock settings in Controls before editing.');
        if(sharedMeta?.configured){
            const location=workspace.locations[index];
            const result=await directoryRequest('/meta-settings/'+encodeURIComponent(location.name),{
                method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({revision:sharedMeta.revision,changes:[{field,day,value}]})
            });
            if(model!==workspace)throw Error('The workspace changed. Reload META before editing.');
            location[field][day]=value;
            const remoteIndex=sharedMeta.locations.findIndex(item=>item.name.toLowerCase()===location.name.toLowerCase());
            if(remoteIndex<0)throw Error('The location is not in the shared META settings. Synchronize locations and retry.');
            sharedMeta.locations[remoteIndex]=result.location;
            sharedMeta.revision=result.revision;
        }
        else workspace.locations[index][field][day]=value;
        queueSave();
        refreshConfigurationIndicators();
    }
    catch(error){
        render(true);
        message(error.message,true)
    }
}
function editChange(event){
    let e=event.target;
    if(e.matches?.('[data-employee-role]')){
        let employeeId=e.dataset.employeeRole,role=e.value;
        if(busy){
            e.value=e.dataset.currentRole||'';
            return
        }
        if(!role){
            e.value=e.dataset.currentRole||'';
            message('Select a role before assigning it.',true);
            return
        }
        busy=true;
        saveEmployeeRoleChanges([employeeId],role).then(changed=>{
            message(changed?'Role updated. The employee is inactive until the updated roster profile is reviewed.':'The employee already has that role.')
        }).catch(error=>{
            e.value=e.dataset.currentRole||'';
            message(error.message,true)
        }).finally(()=>busy=false);
        return
    }
    if(e.matches?.('[data-employee-select]')){
        e.checked?selectedEmployeeIds.add(e.dataset.employeeSelect):selectedEmployeeIds.delete(e.dataset.employeeSelect);
        updateEmployeeSelectionUI();
        return
    }
    if(e.matches?.('[data-employee-select-all]')){
        for(let input of document.querySelectorAll('#content [data-employee-select]')){
            if(input.disabled)continue;
            input.checked=e.checked;
            e.checked?selectedEmployeeIds.add(input.dataset.employeeSelect):selectedEmployeeIds.delete(input.dataset.employeeSelect)
        }
        updateEmployeeSelectionUI();
        return
    }
    if(e.matches?.('[data-publish-group-all]')){
        let group=acceptedPublishGroups()[Number(e.dataset.publishGroupAll)];
        if(!group){
            message('The accepted schedule group could not be found.',true);
            return
        }
        let selections=group.records.flatMap(assignedPublishSelections),groupKeys=new Set(selections.map(item=>JSON.stringify([item.runId,item.day,item.start])));
        if(e.checked){
            let existingKeys=new Set(publishSelection.map(item=>JSON.stringify([item.runId,item.day,item.start]))),additions=selections.filter(item=>!existingKeys.has(JSON.stringify([item.runId,item.day,item.start])));
            if(publishSelection.length+additions.length>500){
                message('Select no more than 500 shifts per publish request.',true);
                render(true);
                return
            }
            publishSelection.push(...additions)
        }
        else publishSelection=publishSelection.filter(item=>!groupKeys.has(JSON.stringify([item.runId,item.day,item.start])));
        publishPreview=null;
        publishResults=[];
        render(true);
        return
    }
    if(e.matches?.('[data-publish-run]')){
        let selection={runId:e.dataset.publishRun,day:Number(e.dataset.publishDay),start:Number(e.dataset.publishStart)};
        if(e.checked){
            let exists=publishSelection.some(item=>item.runId===selection.runId&&item.day===selection.day&&item.start===selection.start);
            if(!exists&&publishSelection.length>=500){
                message('Select no more than 500 shifts per publish request.',true);
                render(true);
                return
            }
            if(!exists)publishSelection.push(selection)
        }
        else publishSelection=publishSelection.filter(item=>!(item.runId===selection.runId&&item.day===selection.day&&item.start===selection.start));
        publishPreview=null;
        publishResults=[];
        render(true);
        return
    }
    if(e.dataset.scheduleShift){
        updateScheduleShift(e);
        return
    }
    if(e.matches?.('input[type=number]')&&e.value!==''&&!e.checkValidity()){
        message('Enter a value within the allowed range and step.',true);
        render(true);
        return
    }
    if(model.locked&&(e.dataset.pool!==undefined||e.dataset.employee!==undefined||e.dataset.control||e.dataset.meta!==undefined)){
        message('Unlock settings in Controls before editing.',true);
        render(true);
        return
    }
    let changed=false,sharedRosterEdit=null;
    if(e.dataset.pool!==undefined){
        let p=model.pools[+e.dataset.pool];
        if(e.dataset.share!==undefined)p.shares[+e.dataset.share]=e.value===''?null:Number(e.value)/100;
        else if(e.dataset.field==='enabled')p.enabled=e.checked;
        changed=true
    }
    if(e.dataset.employee!==undefined){
        let r=model.roster[+e.dataset.employee],k=e.dataset.field,v=e.value;
        if(k==='flex'||k==='reason')r[k]=v;
        else if(k.startsWith('start:')){
            let start=Number(k.slice(6)),permission=v===''?null:Number(v);
            r.shiftAvailability[String(start)]=permission;
            let legacyIndex=STARTS.indexOf(start);
            if(legacyIndex>=0){
                if(!Array.isArray(r.allow))r.allow=Array(4).fill(null);
                r.allow[legacyIndex]=permission
            }
        }
        else if(k.startsWith('day'))r.days[+k.slice(3)]=v===''?null:Number(v);
        else r[k]=v===''?null:Number(v);
        sharedRosterEdit={employee:r,field:k,value:v};
        changed=true
    }
    if(e.dataset.control){
        model.controls[e.dataset.control]=e.dataset.control==='week'?e.value:e.value===''?null:Number(e.value);
        changed=true
    }
    if(e.dataset.meta!==undefined){
        void updateMetaSetting(e);
        return
    }
    if(changed){
        if(sharedRosterEdit&&sharedRoster?.configured){
            void syncSharedRosterEmployeeField(sharedRosterEdit.employee,sharedRosterEdit.field,sharedRosterEdit.value)
                .then(()=>{message('Roster setting saved to the shared business roster.');refreshConfigurationIndicators()})
                .catch(async error=>{
                    message('Roster setting was not synchronized: '+error.message,true);
                    await loadSharedRosterSettings();
                    await saveState();
                    render(true)
                })
        }
        else queueSave();
        refreshConfigurationIndicators()
    }

}
document.addEventListener('change',editChange);
document.addEventListener('change',e=>{
    if(e.target.id!=='businessLogoFile')return;
    let file=e.target.files?.[0];
    if(!file)return;
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>2*1024*1024){
        message('Choose a PNG, JPEG, or WebP logo no larger than 2 MB.',true);
        e.target.value='';
        return
    }
    let reader=new FileReader();
    reader.onload=()=>{
        businessConfig.logoDataUrl=String(reader.result||'');
        render(true);
        message('Logo selected. Save business settings to apply it.')
    };
    reader.onerror=()=>message('The selected logo could not be read.',true);
    reader.readAsDataURL(file)
});
document.addEventListener('input',e=>{
    if(!['tenantIdSetting','bambooTestApiKey'].includes(e.target.id))return;
    bambooPromotionToken='';
    if($('promoteBambooKey'))$('promoteBambooKey').hidden=true;
    if($('businessKeyStatus'))$('businessKeyStatus').textContent=''
});
async function updateScheduleShift(input){
    let original=clone(model),run=model.results.find(item=>item.id===input.dataset.runId),employee=run?.employees.find(item=>item.id===input.dataset.employeeId),day=Number(input.dataset.day);
    if(!run||!employee||!Number.isInteger(day)||day<0||day>6){
        message('The selected schedule shift could not be found.',true);
        render();
        return
    }
    let start=input.value==='off'?null:Number(input.value),starts=run.shiftStarts||STARTS;
    if(start!==null&&(!starts.includes(start)||!employeeCanStart(employee,start))){
        message('That shift start is not enabled for this employee.',true);
        render();
        return
    }
    let previousStart=employee.slots[day],previousType=employee.types[day];
    if(previousStart===start)return;
    employee.slots[day]=start;
    employee.types[day]=start===null?null:'Manual';
    rebuildScheduleAudit(run);
    run.uncovered=[];
    for(let d=0;d<7;d++)for(let index=0;index<starts.length;index++){
        let required=run.requirements[d][index],filled=run.employees.filter(item=>item.slots[d]===starts[index]&&item.types[d]==='Demand').length;
        for(let missing=filled;missing<required;missing++)run.uncovered.push({day:d,start:starts[index],reason:'Manual schedule change'})
    }
    let errors=validateRun(run);
    if(errors.length){
        model=original;
        message('Shift change rejected: '+errors.slice(0,5).join('; '),true);
        render();
        return
    }
    try{
        await saveState();
        if(acceptedSchedules.some(record=>record.id===run.id)){
            await acceptedScheduleRequest('/'+encodeURIComponent(run.id),{
                method:'PUT',body:JSON.stringify(acceptedScheduleSnapshot(run))
            });
            await loadAcceptedSchedules()
        }
        render();
        message('Shift updated and saved.')
    }
    catch(error){
        model=original;
        await saveState();
        message('Shift update was not saved: '+error.message,true);
        render()
    }
}
document.addEventListener('click',async e=>{
    let close=e.target.closest('[data-dialog-close]')?.dataset.dialogClose;
    if(close){
        $(close)?.close();
        return
    }
    let p=e.target.closest('[data-page]');if(p){
        nav(p.dataset.page);return
    }
    let r=e.target.closest('[data-run]');if(r){
        model.selectedRun=r.dataset.run;nav('schedules');return
    }
    let a=e.target.closest('[data-action]');if(a)await action(a.dataset.action,a)
}
);
async function action(a,element=null){
    if(busy)return;
    if(['backup','restore','sourceInputs','sharePointConnect','sharePointDisconnect','sharePointSearch','sharePointOpenDrive','sharePointOpenSiteDrive','sharePointOpenSite','sharePointOpenFolder','sharePointImport','sharePointNext','sharePointBack'].includes(a)&&!pageAllowed('source')){
        message('Source & backups requires the primary business administrator and an enabled page.',true);
        return
    }
    try{
        if(a.startsWith('sharePoint'))await authorizeDataSettings();
        if(a==='tenantLogout'){
            let stateResponse=await fetch('/api/tenant-auth/state');
            let state=await stateResponse.json();
            if(!stateResponse.ok||!state.csrfToken)throw Error(state.error||'Unable to validate the sign-out session.');
            let logoutResponse=await fetch('/api/tenant-auth/logout',{
                method:'POST',
                headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrfToken},
                body:'{}'
            });
            let logoutResult=await logoutResponse.json();
            if(!logoutResponse.ok)throw Error(logoutResult.error||'Sign out failed.');
            window.location.assign('/');
            return
        }
        if(a==='pickBusinessLogo'){
            $('businessLogoFile')?.click();
            return
        }
        if(a==='removeBusinessLogo'){
            businessConfig.logoDataUrl='';
            render(true);
            message('Logo removed from the pending settings. Save business settings to apply the default logo.');
            return
        }
        if(a==='saveBusinessSettings'){
            let config={
                businessName:$('businessNameSetting')?.value.trim(),
                teamName:$('teamNameSetting')?.value.trim(),
                tenantId:$('tenantIdSetting')?.value.trim(),
                primaryColor:$('primaryColorSetting')?.value,
                accentColor:$('accentColorSetting')?.value,
                logoDataUrl:businessConfig.logoDataUrl||''
            };
            bambooPromotionToken='';
            let saved=await directoryRequest('/app-config',{method:'PUT',body:JSON.stringify(config)});
            businessConfig=saved;
            applyBranding();
            render(true);
            message('Business settings saved. The saved tenant now controls BambooHR API requests.');
            return
        }
        if(a==='testBambooKey'){
            let tenantId=$('tenantIdSetting')?.value.trim(),apiKey=$('bambooTestApiKey')?.value;
            if(!tenantId||tenantId!==businessConfig.tenantId)throw Error('Save the tenant settings before testing a key.');
            if(!apiKey?.trim())throw Error('Enter an API key to test.');
            bambooPromotionToken='';
            $('promoteBambooKey').hidden=true;
            $('businessKeyStatus').textContent='Testing read-only BambooHR time-off and time-tracking requests…';
            try{
                let result=await directoryRequest('/bamboohr/validate-key',{method:'POST',body:JSON.stringify({tenantId,apiKey})});
                bambooPromotionToken=result.promotionToken;
                $('bambooTestApiKey').value='';
                $('businessKeyStatus').textContent='Key verified for '+result.tenantId+'. It has not been saved.';
                $('promoteBambooKey').hidden=false
            }
            catch(error){
                $('businessKeyStatus').textContent=error.message;
                throw error
            }
            return
        }
        if(a==='promoteBambooKey'){
            if(!bambooPromotionToken)throw Error('Test a key successfully before promoting it.');
            let result=await directoryRequest('/bamboohr/promote-key',{
                method:'POST',body:JSON.stringify({tenantId:businessConfig.tenantId,promotionToken:bambooPromotionToken})
            });
            bambooPromotionToken='';
            businessConfig.apiKeyConfigured='true';
            $('promoteBambooKey').hidden=true;
            $('businessKeyStatus').textContent='The tested key is now the app’s operational BambooHR API key for '+result.tenantId+'.';
            if($('bambooTestApiKey'))$('bambooTestApiKey').value='';
            render(true);
            message('Tested BambooHR API key saved (encrypted) for this business.');
            return
        }
        if(a==='savePortalSettings'){
            let result=await directoryRequest('/schedule-portal/settings',{
                method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({visibilityWeeks:Number($('portalVisibilityWeeks').value)})
            });
            portalVisibilityWeeks=result.visibilityWeeks;
            message('Schedule portal visibility saved.');
            return
        }
        if(a==='reloadAccessAccounts'){
            await loadAccessAccounts();
            return
        }
        if(a==='deleteSavedSchedule'){
            await deleteSavedSchedule(element.dataset.id);
            return
        }
        if(a==='createAccessAccount'){
            let role=$('accessRole').value,employeeId=$('accessEmployee').value,name=$('accessName').value.trim();
            let result=await directoryRequest('/access-accounts',{
                method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({role,displayName:name,email:$('accessEmail').value.trim(),employeeId:employeeId||undefined})
            });
            accessTemporaryPassword={name:result.account.displayName,password:result.temporaryPassword,hours:result.temporaryPasswordHours};
            await loadAccessAccounts();
            return
        }
        if(a==='resetAccessPassword'){
            let result=await directoryRequest('/access-accounts/'+encodeURIComponent(element.dataset.id)+'/reset-password',{
                method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({resetMfa:element.dataset.resetMfa==='true'})
            });
            let account=accessAccounts.find(item=>item.id===element.dataset.id);
            accessTemporaryPassword={name:account?.displayName||'user',password:result.temporaryPassword,hours:result.temporaryPasswordHours};
            await loadAccessAccounts();
            return
        }
        if(a==='changeAccessRole'){
            openAccessRoleDialog(element.dataset.id);
            return
        }
        if(a==='linkManagerEmployee'){
            if(!confirm('Change this manager employee link and revoke their sessions?'))return;
            await directoryRequest('/access-accounts/'+encodeURIComponent($('managerLinkAccount').value)+'/employee',{
                method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({employeeId:$('managerLinkEmployee').value||null})
            });
            await loadAccessAccounts();
            message('Manager employee link saved; sign in again.');
            return
        }
        if(a==='toggleAccessAccount'){
            await directoryRequest('/access-accounts/'+encodeURIComponent(element.dataset.id)+'/active',{
                method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({active:element.dataset.active==='true'})
            });
            await loadAccessAccounts();
            return
        }
        if(a==='toggleNotifications'){
            toggleNotificationPanel();
            return
        }
        if(a==='openNotification'){
            await openNotification(element.dataset.id);
            return
        }
        if(a==='openTradeApproval'){
            await openTradeApproval(element.dataset.id);
            return
        }
        if(a==='archiveNotification'){
            await archiveNotification(element.dataset.id);
            return
        }
        if(a==='showNotificationArchive'){
            await showNotificationArchive();
            return
        }
        if(a==='showActiveNotifications'){
            showActiveNotifications();
            return
        }
        if(a==='readNotifications'){
            await Promise.all([
                directoryRequest('/attendance/notifications/read',{
                    method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify({})
                }),
                ...pendingTradeNotifications.filter(trade=>trade.unread).map(trade=>directoryRequest('/shift-trades/'+encodeURIComponent(trade.id)+'/read',{
                    method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify({version:trade.version})
                }))
            ]);
            await pollAttendanceNotifications();
            return
        }
        if(a==='reloadDirectory'){
            await loadDirectoryData();
            if(directoryError)throw Error(directoryError);
            render(true);
            return
        }
        if(a==='sortAttendance'){
            let table=element?.dataset.sortTable,key=element?.dataset.sortKey,sort=attendanceSort[table];
            if(!sort||!key)return;
            sort.direction=sort.key===key&&sort.direction==='asc'?'desc':'asc';
            sort.key=key;
            render(true);
            return
        }
        if(a==='syncAttendance'){
            await syncAttendance(false,attendancePeriodRange());
            return
        }
        if(a==='saveAttendanceSource'){
            let source=$('attendanceShiftSource')?.value,attendanceRange=attendancePeriodRange();
            if(source==='bamboohr'&&!window.confirm('Switch attendance to BambooHR scheduled shifts? The app will read and compare BambooHR shifts for the selected period. BambooHR clock events will continue to verify attendance.'))return;
            let result=await directoryRequest('/attendance/source',{
                method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({
                    source,confirmed:source==='bamboohr',
                    start:attendanceRange.start,end:attendanceRange.end
                })
            });
            let refreshed=await syncAttendance(true,attendanceRange);
            render(true);
            if(!refreshed){
                message('Attendance shift source saved, but the selected period could not be refreshed: '+attendanceSyncStatus,true);
                return
            }
            message('Attendance shift source saved: '+(result.selected==='app'?'accepted app shifts.':'BambooHR shifts.'));
            return
        }
        if(a==='reviewAttendanceDiscrepancy'){
            openAttendanceReconciliationDialog(element);
            return
        }
        if(a==='resolveAttendanceDiscrepancy'){
            let reason=$('attendanceReconciliationReason')?.value.trim();
            if(!reason)throw Error('Enter a reason for the shift reconciliation.');
            let attendanceRange=attendancePeriodRange(),result;
            try{
                result=await directoryRequest('/attendance/reconciliation/resolve',{
                    method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                    body:JSON.stringify({
                        confirmed:true,discrepancyId:element.dataset.discrepancyId,
                        direction:element.dataset.direction,date:element.dataset.date,reason
                    })
                })
            }
            catch(error){
                $('attendanceReconciliationDialog')?.close();
                try{
                    await loadAttendanceData(attendanceRange.start,attendanceRange.end);
                    let refreshed=await syncAttendance(true,attendanceRange);
                    render(true);
                    message(
                        refreshed
                            ?error.message
                            :error.message+' Attendance refresh failed: '+attendanceSyncStatus,
                        true
                    )
                }
                catch(refreshError){
                    message(error.message+' Refresh also failed: '+refreshError.message,true)
                }
                return
            }
            $('attendanceReconciliationDialog')?.close();
            let refreshed=await syncAttendance(true,attendanceRange);
            render(true);
            message(
                !refreshed
                    ?'Reconciliation '+result.outcome+' and audited, but attendance refresh failed: '+attendanceSyncStatus
                    :result.outcome==='succeeded'
                        ?'Shift discrepancy resolved and audited.'
                        :'Reconciliation '+result.outcome+'. Review the updated discrepancies.',
                !refreshed
            );
            return
        }
        if(a==='saveAttendanceSettings'){
            let settings={
                latenessToleranceMinutes:Number($('attendanceTolerance')?.value),
                scorePeriodDays:Number($('attendancePeriod')?.value)
            };
            if(!Number.isInteger(settings.latenessToleranceMinutes)||settings.latenessToleranceMinutes<0||settings.latenessToleranceMinutes>120||!Number.isInteger(settings.scorePeriodDays)||settings.scorePeriodDays<30||settings.scorePeriodDays>45)throw Error('Set lateness tolerance from 0 to 120 minutes and the attendance period from 30 to 45 days.');
            let result=await directoryRequest('/attendance/settings',{
                method:'PUT',headers:{'X-CSRF-Token':tenantAuthCsrfToken},body:JSON.stringify(settings)
            });
            if(attendanceData)attendanceData.settings=result.settings;
            await syncAttendance(true);
            render(true);
            message('Attendance rules saved.');
            return
        }
        if(a==='editAttendanceScore'){
            openAttendanceScoreDialog(element);
            return
        }
        if(a==='saveAttendanceScoreOverride'||a==='removeAttendanceScoreOverride'){
            let employeeId=element.dataset.employeeId,reason=$('attendanceOverrideReason')?.value.trim();
            if(!reason)throw Error('Enter a reason for the attendance score override.');
            let options={
                method:a==='saveAttendanceScoreOverride'?'POST':'DELETE',
                headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({reason})
            };
            if(a==='saveAttendanceScoreOverride'){
                let score=$('attendanceOverrideScore')?.value;
                if(score===''||score===undefined||!Number.isFinite(Number(score))||Number(score)<0||Number(score)>100)throw Error('Enter an attendance score from 0 to 100.');
                options.body=JSON.stringify({score:Number(score),reason})
            }
            await directoryRequest('/attendance/scores/'+encodeURIComponent(employeeId)+'/override',options);
            let attendanceRange=attendancePeriodRange();
            await loadAttendanceData(attendanceRange.start,attendanceRange.end);
            $('attendanceOverrideDialog')?.close();
            render(true);
            await saveState();
            message(a==='saveAttendanceScoreOverride'?'Attendance score override saved and audited.':'Attendance score override removed and audited.');
            return
        }
        if(a==='editAttendanceShift'){
            openAttendanceShiftDialog(element);
            return
        }
        if(a==='openAttendanceClockAction'){
            openAttendanceClockActionDialog(element);
            return
        }
        if(a==='submitAttendanceClockAction'){
            let reason=$('attendanceClockActionReason')?.value.trim();
            if(!reason)throw Error('Enter a reason for the BambooHR clock event.');
            busy=true;
            element.disabled=true;
            try{
                const result=await directoryRequest('/attendance/clock-events',{
                    method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                    body:JSON.stringify({
                        action:element.dataset.clockAction,
                        requestId:element.dataset.requestId,
                        runId:element.dataset.runId,
                        employeeId:element.dataset.employeeId,
                        date:element.dataset.shiftDate,
                        reason
                    })
                });
                const attendanceRange=attendancePeriodRange();
                await loadAttendanceData(attendanceRange.start,attendanceRange.end);
                $('attendanceClockActionDialog')?.close();
                render(true);
                message(result.warning||'BambooHR clock event completed and audited.');
            }finally{
                busy=false
            }
            return
        }
        if(a==='saveAttendanceShiftOverride'){
            let reason=$('attendanceShiftReason')?.value.trim();
            if(!reason)throw Error('Enter a reason for the attendance correction.');
            await directoryRequest('/attendance/shifts/override',{
                method:'POST',headers:{'X-CSRF-Token':tenantAuthCsrfToken},
                body:JSON.stringify({
                    runId:element.dataset.runId,employeeId:element.dataset.employeeId,
                    date:element.dataset.shiftDate,status:$('attendanceShiftStatus')?.value,reason
                })
            });
            let attendanceRange=attendancePeriodRange();
            await loadAttendanceData(attendanceRange.start,attendanceRange.end);
            $('attendanceOverrideDialog')?.close();
            render(true);
            message('Attendance correction saved and audited.');
            return
        }
        if(a==='refreshBambooStatus'){
            await loadBambooPublishStatus();
            render(true);
            if(publishError)throw Error(publishError);
            message(publishConfigured?'BambooHR credential is configured.':'The BambooHR API key is not configured. Add it in Settings.',!publishConfigured);
            return
        }
        if(a==='syncBambooEmployees'){
            busy=true;
            employeeSyncStatus='Fetching active employees from BambooHR…';
            render(true);
            try{
                await requestBambooEmployeeSync()
            }
            catch(error){
                employeeSyncStatus='BambooHR sync failed: '+error.message;
                render(true);
                throw error
            }
            return
        }
        if(a==='resolveBambooEmployeeSync'){
            let resolutions=pendingEmployeeSyncConflicts.map((conflict,index)=>{
                let choice=$(`employeeSyncDialog`)?.querySelector(`input[name="sync-person-${index}"]:checked`)?.value;
                if(!choice)throw Error(`Choose whether ${conflict.manualEmployee.name} and ${conflict.bamboohrName} are the same person.`);
                let resolution={bamboohrId:conflict.bamboohrId,employeeId:conflict.manualEmployee.id,samePerson:choice==='same'};
                if(choice==='different'){
                    let newId=$(`employeeSyncDialog`)?.querySelector(`[data-sync-new-id="${index}"]`)?.value.trim();
                    if(!newId)throw Error(`Enter a new Employee ID for manual employee ${conflict.manualEmployee.name}.`);
                    resolution.newManualEmployeeId=newId
                }
                return resolution
            });
            busy=true;
            employeeSyncStatus='Applying reviewed employee reconciliations…';
            render(true);
            try{
                await requestBambooEmployeeSync(resolutions)
            }
            catch(error){
                employeeSyncStatus='BambooHR sync failed: '+error.message;
                render(true);
                throw error
            }
            return
        }
        if(a==='addEmployee'){
            openEmployeeForm();
            return
        }
        if(a==='editEmployee'){
            openEmployeeForm(element.dataset.employeeId);
            return
        }
        if(a==='editEmployeeProfile'){
            let employee=allEmployeeRecords().find(item=>item.id===element.dataset.employeeId);
            if(!employee?.roster)throw Error('The employee roster profile could not be found.');
            filterLoc=employee.location;
            filterRole=employee.role;
            search=employee.name;
            page='roster';
            render();
            requestAnimationFrame(()=>document.querySelector(`[data-roster-employee="${CSS.escape(employee.id)}"]`)?.scrollIntoView({block:'center'}));
            return
        }
        if(a==='toggleEmployee'){
            if(model.locked)throw Error('Unlock settings in Controls before changing employee status.');
            let employee=employeeDirectory.find(item=>item.id===element.dataset.employeeId);
            if(!employee)throw Error('The employee could not be found in the directory.');
            if(!employee.active){
                let rosterEntry=model.roster.find(item=>String(item.id)===employee.id);
                if(!employeeProfileReady(rosterEntry))throw Error('Complete the employee’s Roster settings before making them active.')
            }
            await directoryRequest('/employees/'+encodeURIComponent(employee.id),{
                method:'PUT',body:JSON.stringify({...employee,active:!employee.active})
            });
            await loadDirectoryData();
            await saveState();
            render(true);
            message('Employee status updated.');
            return
        }
        if(a==='batchEmployeeStatus'){
            if(model.locked)throw Error('Unlock settings in Controls before changing employee status.');
            let active=element.dataset.active==='true',employees=employeeDirectory.filter(employee=>selectedEmployeeIds.has(employee.id));
            if(!employees.length||employees.length!==selectedEmployeeIds.size)throw Error('Select one or more employees from the directory.');
            if(active){
                let incomplete=employees.find(employee=>!employeeProfileReady(model.roster.find(item=>String(item.id)===employee.id)));
                if(incomplete)throw Error(`Complete ${incomplete.name}’s Roster settings before making them active.`);
            }
            let status=active?'active':'inactive';
            if(!confirm(`Make ${employees.length} selected employee${employees.length===1?'':'s'} ${status}?`))return;
            await directoryRequest('/employees/status',{
                method:'PUT',body:JSON.stringify({employeeIds:employees.map(employee=>employee.id),active})
            });
            selectedEmployeeIds.clear();
            await loadDirectoryData();
            await saveState();
            render(true);
            message(`${employees.length} employee${employees.length===1?'':'s'} made ${status}.`);
            return
        }
        if(a==='batchEmployeeRole'){
            let role=$('batchEmployeeRole')?.value||'';
            if(!selectedEmployeeIds.size)throw Error('Select one or more employees from the directory.');
            busy=true;
            let changed=await saveEmployeeRoleChanges([...selectedEmployeeIds],role);
            message(changed?`Role assigned to ${changed} employee${changed===1?'':'s'}. Changed employees were made inactive until their roster profiles are reviewed.`:'The selected employees already have that role.');
            return
        }
        if(a==='approveSourceImport'){
            busy=true;
            try{
                await approveSourceImportMappings()
            }
            catch(error){
                message(error.message,true)
            }
            return
        }
        if(a==='deleteEmployee'){
            if(model.locked)throw Error('Unlock settings in Controls before deleting employees.');
            let employee=employeeDirectory.find(item=>item.id===element.dataset.employeeId);
            if(!employee)throw Error('The employee could not be found in the directory.');
            if(!confirm(`Delete ${employee.name} (${employee.id})? Accepted schedule history will remain unchanged.`))return;
            await directoryRequest('/employees/'+encodeURIComponent(employee.id),{method:'DELETE'});
            model.roster=model.roster.filter(item=>String(item.id)!==employee.id);
            model.roster.forEach((item,index)=>item.index=index);
            await loadDirectoryData();
            await saveState();
            render(true);
            message('Employee deleted.');
            return
        }
        if(a==='addScheduleLocation'){
            openScheduleLocationForm();
            return
        }
        if(a==='editScheduleLocation'){
            openScheduleLocationForm(element.dataset.locationId);
            return
        }
        if(a==='deleteScheduleLocation'){
            let location=scheduleLocations.find(item=>item.id===element.dataset.locationId);
            if(!location)throw Error('The schedule location could not be found.');
            if(!confirm(`Delete schedule location "${location.name}"?`))return;
            await directoryRequest('/schedule-locations/'+encodeURIComponent(location.id),{method:'DELETE'});
            await loadDirectoryData();
            await saveState();
            render(true);
            message('Schedule location deleted.');
            return
        }
        if(a==='assignEmployees'){
            if(model.locked)throw Error('Unlock settings in Controls before reassigning employees.');
            openAssignmentDialog(element.dataset.locationId);
            return
        }
        if(a==='stageEmployees'){
            let target=scheduleLocations.find(location=>location.id===assignLocationId);
            if([...assignCandidateIds].some(id=>{
                let employee=employeeDirectory.find(item=>item.id===id);
                return !employee||!target||!roleFitsScheduleGroup(employee.role,target)||!model.pools.some(pool=>pool.location===target.location&&pool.role===employee.role)
            }))throw Error('One or more selected employees do not match this schedule location’s role and location pools.');
            for(let id of assignCandidateIds)assignEmployeeIds.add(id);
            assignCandidateIds.clear();
            renderAssignmentDialog();
            return
        }
        if(a==='unstageEmployees'){
            for(let id of assignCandidateIds)assignEmployeeIds.delete(id);
            assignCandidateIds.clear();
            renderAssignmentDialog();
            return
        }
        if(a==='saveAssignments'){
            await saveEmployeeAssignments();
            return
        }
        if(a==='previewPublish'){
            let response=await directoryRequest('/bamboohr/preview',{method:'POST',body:JSON.stringify({selections:publishSelection})});
            publishPreview=response.payloads;
            publishResults=[];
            render(true);
            message('Preview is ready. No BambooHR changes have been posted.');
            return
        }
        if(a==='clearPublishSelection'){
            publishSelection=[];
            publishPreview=null;
            publishResults=[];
            render(true);
            return
        }
        if(a==='openPublishConfirm'){
            if(!publishPreview?.length)throw Error('Preview the selected shifts before publishing.');
            let dialog=$('bambooPublishDialog');
            dialog.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">EXPLICIT CONFIRMATION</div><h2>Post ${publishPreview.length} BambooHR schedule entries?</h2></div><button type="button" data-dialog-close="bambooPublishDialog" aria-label="Close">✕</button></div><p>This will send accepted shift assignments to BambooHR. Confirm only after reviewing the selected schedules and employee IDs.</p><div class="tablewrap"><table><thead><tr><th>Schedule</th><th>Start</th><th>Employees</th><th>BambooHR IDs</th></tr></thead><tbody>${publishPreview.map(item=>`<tr><td>${esc(item.scheduleName)}</td><td>${esc(item.start)}</td><td>${esc(item.employeeNames.join(', '))}</td><td>${esc(item.employeeIds.join(', '))}</td></tr>`).join('')}</tbody></table></div><div class="actions"><button type="button" data-dialog-close="bambooPublishDialog">Cancel</button><button type="button" class="danger" data-action="confirmPublish">Confirm and post to BambooHR</button></div>`;
            dialog.showModal();
            return
        }
        if(a==='confirmPublish'){
            let response=await fetch('/api/bamboohr/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true,selections:publishSelection})});
            let body=await response.json().catch(()=>({}));
            publishResults=body.results||[];
            $('bambooPublishDialog').close();
            if(!response.ok){
                publishPreview=null;
                render(true);
                message(body.error||'BambooHR publish failed with HTTP '+response.status+'.',true);
                return
            }
            publishPreview=null;
            render(true);
            message('BambooHR publishing completed. Review the per-schedule results below.',publishResults.some(result=>!result.success));
            return
        }
        if(a==='sourcePicker'){
            await openSourcePicker();
            return
        }
        if(a==='closeSourcePicker'){
            $('sourcePickerDialog').close();
            return
        }
        if(a==='sharePointConnect'){
            await connectMicrosoftAccount();
            return
        }
        if(a==='sharePointDisconnect'){
            await disconnectMicrosoftAccount();
            return
        }
        if(a==='sharePointSearch'){
            await searchSharePointSites();
            return
        }
        if(a==='sharePointOpenSite'){
            await openSharePointSite(element.dataset.id,element.dataset.name);
            return
        }
        if(a==='sharePointOpenDrive'||a==='sharePointOpenSiteDrive'){
            await openSharePointDrive(element.dataset.id,element.dataset.name,a==='sharePointOpenSiteDrive'?'siteDrive':'drive');
            return
        }
        if(a==='sharePointOpenFolder'){
            sharePointState.folderStack.push({id:element.dataset.id,name:element.dataset.name});
            await loadSharePointFolder(element.dataset.id);
            return
        }
        if(a==='sharePointImport'){
            await importSharePointWorkbook(sharePointState.driveId,element.dataset.id,element.dataset.name);
            return
        }
        if(a==='sharePointNext'){
            await loadNextSharePointPage();
            return
        }
        if(a==='sharePointBack'){
            await goBackInSharePoint();
            return
        }
        if(a==='timeOffWorkbook'){
            openTimeOffs();
            return
        }
        if(a==='profile'){
            openUserProfile();
            return
        }
        if(a==='timeOffs'){
            openTimeOffs();
            return
        }
        if(a==='addAppLocation'){
            openAppLocationDialog();
            return
        }
        if(a==='addLocationRole'){
            openLocationRoleDialog();
            return
        }
        if(a==='acceptBambooLocations'){
            await acceptSelectedBambooLocations();
            return
        }
        if(a==='initializeSharedRoster'){
            await initializeSharedRoster();
            return
        }
        if(a==='syncSharedRosterEmployees'){
            await syncMissingSharedRosterEmployees();
            return
        }
        if(a==='syncSharedRosterPools'){
            await syncSharedRosterPools();
            return
        }
        if(a==='initializeSharedMeta'){
            await initializeSharedMeta();
            return
        }
        if(a==='syncSharedMetaLocations'){
            await syncSharedMetaLocations();
            return
        }
        if(a==='reloadSharedMeta'){
            await loadSharedMetaSettings();
            render(true);
            return
        }
        if(a==='reloadSharedRoster'){
            await loadSharedRosterSettings();
            render(true);
            return
        }
        if(a==='refreshTimeOffs'){
            await refreshTimeOffFromServer();
            return
        }
        if(a==='trade'){
            openTrades();
            return
        }
        if(a==='scheduleUpload'){
            openScheduleImport();
            return
        }
        if(a==='scheduleTemplate'){
            await downloadScheduleTemplate();
            return
        }
        if(a==='addShiftStart'){
            if(model.locked)throw Error('Unlock settings in Controls before adding a shift start.');
            const previous=clone(model);
            let pool=model.pools[Number(element.dataset.poolIndex)],field=document.querySelector(`[data-new-shift-start="${element.dataset.poolIndex}"]`),start=parseStartTime(field?.value);
            if(!pool)throw Error('The selected location-role pool could not be found.');
            if(start===null)throw Error('Enter a valid start time in 15-minute increments.');
            if(poolStarts(pool).includes(start))throw Error('That shift start is already configured for this pool.');
            let configured=poolStarts(pool).map((value,index)=>[value,pool.shares[index]]).concat([[start,0]]).sort((left,right)=>left[0]-right[0]);
            pool.shiftStarts=configured.map(([value])=>value);
            pool.shares=configured.map(([,share])=>share);
            for(let employee of poolRoster(model,p))employee.shiftAvailability[String(start)]=0;
            field.value='';
            await saveState();
            try{
                await saveSharedRosterConfiguration(model.locked,model.pools.map(item=>({location:item.location,role:item.role,starts:poolStarts(item).map(Number)})));
                await loadSharedRosterSettings()
            }
            catch(error){
                model=previous;
                await saveState();
                throw error
            }
            render(true);
            message(timeLabel(start)+' added to '+pool.location+' · '+pool.role+'. Set the share and employee availability before locking.');
            return
        }
        if(a==='removeShiftStart'){
            if(model.locked)throw Error('Unlock settings in Controls before removing a shift start.');
            const previous=clone(model);
            let pool=model.pools[Number(element.dataset.poolIndex)],start=Number(element.dataset.shiftStart);
            if(!pool||!poolStarts(pool).includes(start))throw Error('The selected shift start could not be found.');
            if(poolStarts(pool).length<=1)throw Error('Each location-role pool must keep at least one shift start.');
            let affected=poolRoster(model,pool).filter(employee=>employee.preferred===start).map(employee=>employee.name);
            if(affected.length)throw Error('Update the preferred start for '+affected.join(', ')+' before removing '+timeLabel(start)+'.');
            let index=poolStarts(pool).indexOf(start);
            let sharesValid=pool.shares.length===poolStarts(pool).length&&pool.shares.every(share=>isNum(share)&&share>=0&&share<=1)&&Math.abs(pool.shares.reduce((total,share)=>total+share,0)-1)<.0001;
            let removedShare=pool.shares[index],remainingShares=pool.shares.filter((_,shareIndex)=>shareIndex!==index),remainingTotal=remainingShares.reduce((total,share)=>total+(isNum(share)?Number(share):0),0);
            pool.shiftStarts.splice(index,1);
            pool.shares=sharesValid?remainingShares.map(share=>remainingTotal>0?Number(share)+removedShare*Number(share)/remainingTotal:1/remainingShares.length):remainingShares;
            for(let employee of poolRoster(model,pool))delete employee.shiftAvailability[String(start)];
            await saveState();
            try{
                await saveSharedRosterConfiguration(model.locked,model.pools.map(item=>({location:item.location,role:item.role,starts:poolStarts(item).map(Number)})));
                await loadSharedRosterSettings()
            }
            catch(error){
                model=previous;
                await saveState();
                throw error
            }
            render(true);
            message(timeLabel(start)+' removed from '+pool.location+' · '+pool.role+'.'+(sharesValid?' The existing allocation was redistributed across remaining starts.':' Review and allocate the remaining shares before locking.'));
            return
        }
        if(a==='acceptSchedule'){
            let run=model.results.find(item=>item.id===element.dataset.runId);
            if(!run)throw Error('The selected schedule could not be found.');
            await acceptedScheduleRequest('',{method:'POST',body:JSON.stringify(acceptedScheduleSnapshot(run))});
            await loadAcceptedSchedules();
            render();
            message('Schedule accepted and saved to the app database.');
            return
        }
        if(a==='undoAccept'){
            let runId=element.dataset.runId;
            if(!runId)throw Error('The accepted schedule could not be identified.');
            if(!confirm('Undo acceptance for this schedule? The generated workspace schedule will remain unchanged.'))return;
            await acceptedScheduleRequest('/'+encodeURIComponent(runId),{method:'DELETE'});
            publishSelection=publishSelection.filter(selection=>selection.runId!==runId);
            publishPreview=null;
            publishResults=[];
            await loadAcceptedSchedules();
            render();
            message('Schedule acceptance undone. The generated workspace schedule remains unchanged.');
            return
        }
        if(a==='downloadVisible'){
            downloadFile('CBL-Filtered-Schedules.xlsx',workbookBlob(exportTables(visibleScheduleRuns())));
            return
        }
        if(a==='refresh'){
            await refreshSchedules();
            return
        }
        if(a==='undoShuffle'){
            await undoShuffle();
            return
        }
        if(a==='email'){
            openEmail();
            return
        }
        if(a==='lock'){
            let check=modelIssues(model);
            if(check.errors.length){
                page='controls';
                render();
                message('Resolve '+check.errors.length+' blocking issues before locking.',true);
                return
            }
            let oldLocked=model.locked,oldTime=model.lockedAt;
            model.locked=true;
            model.lockedAt=new Date().toISOString();
            try{
                await saveState();
                await saveSharedRosterConfiguration(true,model.pools.map(item=>({location:item.location,role:item.role,starts:poolStarts(item).map(Number)})));
                if(!sharedRoster?.configured&&sharedMeta?.configured)await saveSharedMetaConfiguration(true,sharedMeta.locations);
                await loadSharedMetaSettings()
            }
            catch(e){
                model.locked=oldLocked;
                model.lockedAt=oldTime;
                await saveState();
                throw e
            }
            message('Configuration locked. Generate schedules when ready.');
            render()
        }
        else if(a==='unlock'){
            model.previousScheduleSet=null;
            model.locked=false;
            model.revision++;
            try{
                await saveState();
                await saveSharedRosterConfiguration(false,sharedRoster?.configured?sharedRoster.pools:model.pools.map(item=>({location:item.location,role:item.role,starts:poolStarts(item).map(Number)})));
                if(!sharedRoster?.configured&&sharedMeta?.configured)await saveSharedMetaConfiguration(false,sharedMeta.locations);
                await loadSharedMetaSettings()
            }
            catch(e){
                model.locked=true;
                model.revision--;
                await saveState();
                throw e
            }
            message('Settings unlocked. Existing schedules retain their saved snapshots.');
            render()
        }
        else if(a==='generate'){
            busy=true;
            message('Checking BambooHR time-offs and generating all enabled pools…');
            await prepareGenerationTimeOff();
            await new Promise(r=>setTimeout(r,10));
            let runs=generateAll(model);
            for(let attempt=0;attempt<15;attempt++){
                let prior=runs.map(r=>model.results.find(b=>b.id===r.id));
                if(prior.some((b,i)=>!b||scheduleFingerprint(b)!==scheduleFingerprint(runs[i])))break;
                runs=generateAll(model)
            }
            for(let r of runs){
                let failures=validateRun(r);
                if(failures.length)throw Error('Schedule validation failed: '+failures.join('; '))
            }
            let old=clone(model.results),selected=model.selectedRun;
            model.previousScheduleSet=null;
            model.controls={
                ...model.controls,shuffle:true,seed:runs[0]?.controls.seed??model.controls.seed
            }
            ;
            for(let r of runs){
                model.db.Controls[3][1]=r.location;
                model.db.Controls[14][1]=r.role;
                model.db.Controls[4][1]=r.start;
                let i=model.results.findIndex(x=>x.id===r.id);
                if(i>=0)model.results[i]=r;
                else model.results.push(r)
            }
            model.selectedRun=runs[0]?.id||'';
            try{
                await saveState()
            }
            catch(err){
                model.results=old;
                model.selectedRun=selected;
                throw Error('Schedules generated but could not be saved: '+err.message)
            }
            page='schedules';
            render();
            message(runs.length+(storageMode==='session'?' weekly schedules generated in this session. Save a workspace backup or portable ZIP bundle before closing.':' weekly schedules generated and saved. Review unfilled demand and employee shortfalls.')+timeOffSummary(),(model.bambooTimeOff?.status==='error'||model.bambooTimeOff?.apiStatus==='error'))
        }
        else if(a==='download')downloadSchedules();
        else if(a==='csv')downloadCSV();
        else if(a==='backup'){
            await authorizeDataSettings('backup');
            downloadFile('CBL-Scheduling-Workspace.json',new Blob([JSON.stringify({
                version:1,model
            }
            )],{
                type:'application/json'
            }
            ));
        }
        else if(a==='restore')$('restoreUpload').click();
        else if(a==='portable')await portable();
        else if(a==='sourceInputs')await downloadInputs()
    }
    catch(err){
        if(a.startsWith('sharePoint'))setSharePointStatus(err.message,true);
        message(err.message,true)
    }
    finally{
        busy=false
    }

}
function store(action,value,recordKey='current'){
    return new Promise((resolve,reject)=>{
        let db,tx,done=false,timer;function finish(err,out){
            if(done)return;done=true;clearTimeout(timer);if(db)db.close();err?reject(err):resolve(out)
        }
        try{
            if(typeof indexedDB==='undefined')return finish(Error('Browser storage unavailable'));let request=indexedDB.open('cbl-scheduling-v1:'+location.pathname,1);timer=setTimeout(()=>{
                try{
                    tx?.abort()
                }
                catch{

                }
                finish(Error('Storage timed out'))
            }
            ,12000);request.onupgradeneeded=()=>{
                if(!request.result.objectStoreNames.contains('workspace'))request.result.createObjectStore('workspace')
            }
            ;request.onblocked=()=>finish(Error('Browser storage is blocked'));request.onerror=()=>finish(request.error||Error('Browser storage denied'));request.onsuccess=()=>{
                db=request.result;if(done){
                    db.close();return
                }
                try{
                    let writing=action==='put'||action==='delete';tx=db.transaction('workspace',writing?'readwrite':'readonly');let store=tx.objectStore('workspace'),rq=action==='put'?store.put(value,recordKey):action==='delete'?store.delete(recordKey):store.get(recordKey),out;rq.onsuccess=()=>out=rq.result;tx.oncomplete=()=>finish(null,out);tx.onerror=tx.onabort=()=>finish(tx.error||Error('Storage write failed'))
                }
                catch(err){
                    finish(err)
                }

            }

        }
        catch(err){
            finish(err)
        }

    }
    )
}
function storageStatus(){
    let warning=$('storageWarning');
    if(warning){
        warning.hidden=storageMode!=='session';
        warning.textContent=storageMode==='session'?'Session mode: this context blocks browser storage. Locking, uploads and scheduling still work. Before closing or refreshing, download the portable ZIP bundle when hosted or download a workspace backup from Source & backups.':''
    }
    $('savedState').textContent=storageMode==='session'?'Session only · automatic browser saving unavailable':'Saved in this browser · '+new Date().toLocaleTimeString();
    updateHeaderNotices()
}
async function persistWorkspace(value){
    if(storageMode==='session'){
        storageStatus();
        return false
    }
    try{
        await store('put',value);
        storageMode='persistent';
        storageStatus();
        return true
    }
    catch(err){
        storageMode='session';
        storageReason=err.message;
        storageStatus();
        return false
    }

}
async function saveState(){
    return persistWorkspace(model)
}
const microsoftAuthScopes=['Files.Read'];
const microsoftConsumerTenantId='9188040d-6c67-4c5b-b112-36a304b66dad';
const microsoftAuthLibraryUrl='https://cdn.jsdelivr.net/npm/@azure/msal-browser@4.7.0/lib/msal-browser.min.js';
let microsoftAuthClient=null;
let sharePointAccount=null;
let sharePointState={
    view:'drives',
    items:[],
    siteResults:[],
    nextLink:null,
    driveId:'',
    driveName:'',
    siteName:'',
    driveReturnView:'drives',
    folderStack:[]
};
function microsoftAuthReadiness(){
    let clientId=String(window.CBL_MICROSOFT_CLIENT_ID||'').trim();
    if(!/^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(clientId))return 'Set a valid Entra application client ID in CBL-Scheduler2.config.js to enable sign-in.';
    let localHost=['localhost','127.0.0.1','[::1]'].includes(location.hostname);
    if(location.protocol!=='https:'&&!(location.protocol==='http:'&&localHost))return 'Microsoft sign-in requires HTTPS or a localhost web server. It is not available from file://.';
    let redirectUri;
    try{
        redirectUri=new URL(microsoftRedirectUri())
    }
    catch{
        return 'Set a valid Microsoft sign-in redirect URI in CBL-Scheduler2.config.js.'
    }
    if(redirectUri.origin!==location.origin||redirectUri.search||redirectUri.hash)return 'The redirect URI must use this app’s origin and must not include a query or fragment.';
    return ''
}
function microsoftRedirectUri(){
    return String(window.CBL_MICROSOFT_REDIRECT_URI||'').trim()||new URL('CBL-MicrosoftAuth.html',location.href).href
}
function updateMicrosoftConfigNotice(){
    let notice=$('sharePointConfigNotice'),button=$('sharePointConnect'),redirect=$('sharePointRedirectUri');
    let readiness=microsoftAuthReadiness();
    if(notice)notice.textContent=readiness||'Ready to connect. Sign-in tokens stay in memory and are not included in workspace backups.';
    if(button)button.disabled=!!readiness;
    if(redirect)redirect.textContent=microsoftRedirectUri();
    return readiness
}
async function openSourcePicker(){
    try{await authorizeDataSettings();}
    catch(error){message(error.message,true);return;}
    if(!pageAllowed('source')){
        message('Source & backups requires the primary business administrator and an enabled page.',true);
        return
    }
    updateMicrosoftConfigNotice();
    $('sourcePickerDialog').showModal()
}
function setSharePointStatus(text,error=false){
    let status=$('sharePointStatus');
    if(status){
        status.textContent=text;
        status.classList.toggle('error',error)
    }
}
function renderSharePointItems(){
    let list=$('sharePointItems'),title=$('sharePointListingTitle'),back=$('sharePointBack'),next=$('sharePointNext');
    if(!list)return;
    if(sharePointState.view==='sites'){
        list.replaceChildren();
        title.textContent='SharePoint site search results';
        back.hidden=true;
        next.hidden=true;
        return
    }
    list.innerHTML=sharePointState.items.map(item=>{
        let action=item.kind==='drive'?'sharePointOpenDrive':item.kind==='siteDrive'?'sharePointOpenSiteDrive':item.kind==='folder'?'sharePointOpenFolder':'sharePointImport';
        let detail=item.kind==='drive'?item.driveType||'Drive':item.kind==='siteDrive'?'Document library':item.kind==='folder'?'Folder':Math.ceil((item.size||0)/1024)+' KB';
        return `<button type="button" data-action="${action}" data-id="${esc(item.id)}" data-name="${esc(item.name)}"><span>${esc(item.kind==='folder'?'📁':item.kind==='file'?'📄':'▸')} ${esc(item.name)}</span><small>${esc(detail)}</small></button>`
    }).join('')||`<p class="note">${sharePointState.view==='files'?'No folders or .xlsx workbooks found here.':'No drives or document libraries are available.'}</p>`;
    title.textContent=sharePointState.view==='files'?(sharePointState.folderStack.map(x=>x.name).join(' / ')||sharePointState.driveName):sharePointState.view==='siteDrives'?(sharePointState.siteName+' · document libraries'):'Your files';
    back.hidden=!['files','siteDrives'].includes(sharePointState.view);
    next.hidden=!sharePointState.nextLink
}
function renderSharePointSites(){
    $('sharePointSiteResults').innerHTML=sharePointState.siteResults.map(site=>`<button type="button" data-action="sharePointOpenSite" data-id="${esc(site.id)}" data-name="${esc(site.displayName||site.name)}"><span>▣ ${esc(site.displayName||site.name)}</span><small>SharePoint site</small></button>`).join('');
    if(sharePointState.siteResults.length)$('sharePointListingTitle').textContent='Search results · select a site';
}
async function loadMicrosoftIdentityLibrary(){
    if(window.msal?.PublicClientApplication)return window.msal;
    await new Promise((resolve,reject)=>{
        let script=document.createElement('script');
        script.src=microsoftAuthLibraryUrl;
        script.crossOrigin='anonymous';
        script.onload=resolve;
        script.onerror=()=>reject(Error('Microsoft sign-in library could not be loaded. Check your internet connection and content security policy.'));
        document.head.appendChild(script)
    });
    if(!window.msal?.PublicClientApplication)throw Error('Microsoft sign-in library loaded without the expected API.');
    return window.msal
}
async function getMicrosoftAuthClient(){
    if(microsoftAuthClient)return microsoftAuthClient;
    let msal=await loadMicrosoftIdentityLibrary(),clientId=String(window.CBL_MICROSOFT_CLIENT_ID||'').trim();
    let redirectUri=microsoftRedirectUri();
    microsoftAuthClient=new msal.PublicClientApplication({
        auth:{
            clientId,
            authority:'https://login.microsoftonline.com/common',
            redirectUri
        },
        cache:{
            cacheLocation:'memoryStorage'
        }
    });
    await microsoftAuthClient.initialize();
    await microsoftAuthClient.handleRedirectPromise();
    return microsoftAuthClient
}
async function getMicrosoftAccessToken(scopes=microsoftAuthScopes){
    let client=await getMicrosoftAuthClient(),msal=window.msal,account=sharePointAccount||client.getActiveAccount();
    if(!account){
        let result=await client.loginPopup({scopes:microsoftAuthScopes});
        account=result.account;
        sharePointAccount=account;
        client.setActiveAccount(account)
    }
    try{
        let result=await client.acquireTokenSilent({scopes,account});
        return result.accessToken
    }
    catch(error){
        if(!(error instanceof msal.InteractionRequiredAuthError))throw error;
        let result=await client.acquireTokenPopup({scopes,account});
        return result.accessToken
    }
}
function microsoftGraphUrl(path){
    let url=new URL(path,'https://graph.microsoft.com/v1.0/');
    if(url.origin!=='https://graph.microsoft.com'||!url.pathname.startsWith('/v1.0/'))throw Error('Unexpected Microsoft Graph URL.');
    return url
}
async function microsoftGraphRequest(path,scopes=microsoftAuthScopes){
    let token=await getMicrosoftAccessToken(scopes),response;
    try{
        response=await fetch(microsoftGraphUrl(path),{
            headers:{Authorization:'Bearer '+token}
        })
    }
    catch(error){
        if(error instanceof TypeError)throw Error('Microsoft Graph could not be reached. Check connectivity, browser network restrictions, and CORS policy.');
        throw error
    }
    if(!response.ok){
        let result=await response.json();
        throw Error(result.error?.message||`Microsoft Graph request failed (HTTP ${response.status}).`)
    }
    return response
}
async function microsoftGraphJson(path,scopes=microsoftAuthScopes){
    return (await microsoftGraphRequest(path,scopes)).json()
}
async function connectMicrosoftAccount(){
    let readiness=updateMicrosoftConfigNotice();
    if(readiness)throw Error(readiness);
    setSharePointStatus('Opening Microsoft sign-in…');
    let client=await getMicrosoftAuthClient(),result=await client.loginPopup({scopes:microsoftAuthScopes});
    sharePointAccount=result.account;
    client.setActiveAccount(sharePointAccount);
    $('sharePointAccount').textContent='Connected as '+(sharePointAccount.username||sharePointAccount.name||'Microsoft account');
    $('sharePointAccount').hidden=false;
    $('sharePointConnect').hidden=true;
    $('sharePointDisconnect').hidden=false;
    $('sharePointBrowser').hidden=false;
    let isPersonal=sharePointAccount.tenantId===microsoftConsumerTenantId;
    $('sharePointSiteSearch').closest('.sharepoint-search').hidden=isPersonal;
    $('sharePointSiteResults').replaceChildren();
    sharePointState.siteResults=[];
    setSharePointStatus(isPersonal?'Personal account connected. Loading your available files…':'Work or school account connected. Loading your available drives…');
    await loadSharePointDrives()
}
async function loadSharePointDrives(){
    sharePointState.view='drives';
    sharePointState.driveId='';
    sharePointState.siteName='';
    sharePointState.folderStack=[];
    sharePointState.returnListing=null;
    let result=await microsoftGraphJson('me/drives?$select=id,name,driveType,webUrl&$top=100');
    sharePointState.items=(result.value||[]).map(drive=>({
        kind:'drive',id:drive.id,name:drive.name,driveType:drive.driveType
    }));
    sharePointState.nextLink=result['@odata.nextLink']||null;
    renderSharePointItems();
    setSharePointStatus('Select a drive, library, folder, or .xlsx workbook.')
}
async function searchSharePointSites(){
    if(!sharePointAccount||sharePointAccount.tenantId===microsoftConsumerTenantId)throw Error('SharePoint site search is available for work or school accounts only.');
    let query=$('sharePointSiteSearch').value.trim();
    if(!query)throw Error('Enter a site name to search.');
    setSharePointStatus('Searching SharePoint sites…');
    let result=await microsoftGraphJson('sites?search='+encodeURIComponent(query)+'&$select=id,name,displayName,webUrl&$top=25',['Sites.Read.All']);
    sharePointState.siteResults=result.value||[];
    sharePointState.view='sites';
    renderSharePointSites();
    renderSharePointItems();
    setSharePointStatus(sharePointState.siteResults.length?'Select a site to browse its document libraries.':'No accessible SharePoint sites matched that search.')
}
async function openSharePointSite(siteId,siteName){
    setSharePointStatus('Loading document libraries…');
    let result=await microsoftGraphJson('sites/'+encodeURIComponent(siteId)+'/drives?$select=id,name,driveType,webUrl&$top=100',['Sites.Read.All']);
    sharePointState.view='siteDrives';
    sharePointState.siteName=siteName;
    sharePointState.driveReturnView='siteDrives';
    sharePointState.items=(result.value||[]).map(drive=>({
        kind:'siteDrive',id:drive.id,name:drive.name,driveType:drive.driveType
    }));
    sharePointState.nextLink=result['@odata.nextLink']||null;
    renderSharePointItems();
    setSharePointStatus(sharePointState.items.length?'Select a document library.':'No document libraries are available for this site.')
}
async function openSharePointDrive(driveId,driveName,kind='drive'){
    sharePointState.driveReturnView=kind==='siteDrive'?'siteDrives':'drives';
    sharePointState.returnListing={
        view:sharePointState.view,
        items:sharePointState.items,
        nextLink:sharePointState.nextLink
    };
    sharePointState.driveId=driveId;
    sharePointState.driveName=driveName;
    sharePointState.folderStack=[];
    await loadSharePointFolder(null)
}
async function loadSharePointFolder(folderId,append=false,nextLink=''){
    let path=nextLink||('drives/'+encodeURIComponent(sharePointState.driveId)+(folderId?'/items/'+encodeURIComponent(folderId)+'/children':'/root/children')+'?$select=id,name,folder,file,size&$top=100');
    setSharePointStatus('Loading folders and workbooks…');
    let result=await microsoftGraphJson(path);
    let items=(result.value||[]).filter(item=>item.folder||item.file&&/\.xlsx$/i.test(item.name||'')).map(item=>({
        kind:item.folder?'folder':'file',id:item.id,name:item.name,size:item.size
    })).sort((a,b)=>Number(b.kind==='folder')-Number(a.kind==='folder')||a.name.localeCompare(b.name));
    sharePointState.view='files';
    sharePointState.items=append?sharePointState.items.concat(items):items;
    sharePointState.nextLink=result['@odata.nextLink']||null;
    renderSharePointItems();
    setSharePointStatus(items.length?'Choose a folder or an .xlsx workbook.':'No folders or .xlsx workbooks found here.')
}
async function loadNextSharePointPage(){
    if(!sharePointState.nextLink)return;
    if(sharePointState.view==='files'){
        await loadSharePointFolder(sharePointState.folderStack.at(-1)?.id||null,true,sharePointState.nextLink);
        return
    }
    let result=await microsoftGraphJson(sharePointState.nextLink,sharePointState.view==='siteDrives'?['Sites.Read.All']:microsoftAuthScopes);
    let kind=sharePointState.view==='siteDrives'?'siteDrive':'drive';
    sharePointState.items=sharePointState.items.concat((result.value||[]).map(item=>({
        kind,id:item.id,name:item.name,driveType:item.driveType
    })));
    sharePointState.nextLink=result['@odata.nextLink']||null;
    renderSharePointItems()
}
async function goBackInSharePoint(){
    if(sharePointState.view==='siteDrives'){
        sharePointState.view='sites';
        sharePointState.items=[];
        renderSharePointItems();
        setSharePointStatus('Select a SharePoint site from the search results.')
    }
    else if(sharePointState.folderStack.length){
        sharePointState.folderStack.pop();
        await loadSharePointFolder(sharePointState.folderStack.at(-1)?.id||null)
    }
    else{
        let listing=sharePointState.returnListing;
        sharePointState.view=listing?.view||sharePointState.driveReturnView;
        sharePointState.items=listing?.items||[];
        sharePointState.nextLink=listing?.nextLink||null;
        sharePointState.returnListing=null;
        renderSharePointItems();
        setSharePointStatus(sharePointState.view==='siteDrives'?'Select a document library.':'Select a drive.')
    }
}
async function importSharePointWorkbook(driveId,itemId,fileName){
    setSharePointStatus('Downloading the selected workbook…');
    let response=await microsoftGraphRequest('drives/'+encodeURIComponent(driveId)+'/items/'+encodeURIComponent(itemId)+'/content');
    let blob=await response.blob();
    if(blob.size>60e6)throw Error('Workbook exceeds 60 MB.');
    let file=new File([blob],fileName,{type:blob.type||'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
    if(await importSourceFile(file))$('sourcePickerDialog').close();
    else setSharePointStatus('Workbook was not imported. Review the error message and try again.',true)
}
async function disconnectMicrosoftAccount(){
    let clearError=null;
    try{
        if(microsoftAuthClient)await microsoftAuthClient.clearCache()
    }
    catch(error){
        clearError=error
    }
    finally{
        sharePointAccount=null;
        microsoftAuthClient?.setActiveAccount(null);
        sharePointState={
            view:'drives',items:[],siteResults:[],nextLink:null,driveId:'',driveName:'',siteName:'',driveReturnView:'drives',folderStack:[]
        };
        $('sharePointAccount').hidden=true;
        $('sharePointConnect').hidden=false;
        $('sharePointDisconnect').hidden=true;
        $('sharePointBrowser').hidden=true;
        $('sharePointSiteResults').replaceChildren();
        $('sharePointItems').replaceChildren();
        updateMicrosoftConfigNotice();
        setSharePointStatus(clearError?'Sign-out could not clear Microsoft’s in-memory cache: '+clearError.message:'Disconnected. Microsoft sign-in data was cleared from memory.',!!clearError)
    }
    if(clearError)throw clearError
}
async function importSource(e){
    let file=e.target.files[0];
    e.target.value='';
    await importSourceFile(file)
}
async function importSourceFile(file){
    if(!pageAllowed('source')){
        message('Source & backups requires the primary business administrator and an enabled page.',true);
        return false
    }
    if(!file)return false;
    if(busy){
        return false
    }
    busy=true;
    try{
        await authorizeDataSettings('source-import');
        message('Reading and validating source workbook…');
        let bytes=await file.arrayBuffer();
        if(bytes.byteLength>60e6)throw Error('Workbook exceeds 60 MB');
        let db=await parseXlsx(bytes),next=fromWorkbook(db,file.name);
        next.controls.weeks=scheduleWeeks(model);
        next.results=model?.results||[];
        next.revision=(model?.revision||0)+1;
        next.theme=model?.theme||'light';
        next.settings=clone(appSettings());
        next.overtime=clone(overtimeConfig());
        next.user=clone(model.user||{

        }
        );
        next.bambooTimeOff=clone(model.bambooTimeOff||null);
        next.timeOffWorkbook=clone(model.timeOffWorkbook||null);
        openSourceImportReview(next);
        message('Workbook validated. Review and approve every employee mapping before importing.');
        return true
    }
    catch(err){
        message('Import failed; previous workspace retained. '+err.message,true);
        return false
    }
    finally{
        busy=false
    }

}
async function restoreWorkspace(e){
    if(!pageAllowed('source')){
        e.target.value='';
        message('Source & backups requires the primary business administrator and an enabled page.',true);
        return
    }
    let file=e.target.files[0];
    if(!file)return;
    try{
        await authorizeDataSettings('restore');
        let backup=JSON.parse(await file.text()),m=backup.model;
        if(backup.version!==1||!m||!Array.isArray(m.roster)||!Array.isArray(m.pools)||!m.controls||!Array.isArray(m.results))throw Error('Invalid workspace backup');
        migrateScheduleWeeks(m);
        let otErrors=overtimeIssues(m);
        if(otErrors.length)throw Error(otErrors.join('; '));
        for(let r of m.results)if(validateRun(r).length)throw Error('Backup contains a schedule that fails constraint checks');
        await persistWorkspace(m);
        model=m;
        filterLoc=filterRole='All';
        render();
        message(storageMode==='session'?'Workspace restored for this session. Save a backup; hosted apps can also download the portable ZIP bundle before closing.':'Workspace restored and saved.')
    }
    catch(err){
        message('Restore failed: '+err.message,true)
    }
    finally{
        e.target.value=''
    }

}
async function portableHtmlBlob(){
    let bytes=new TextEncoder().encode(JSON.stringify(model)),gzip=new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer()),base='';
    for(let b of gzip)base+=String.fromCharCode(b);
    let doc=document.documentElement.cloneNode(true);
    doc.querySelectorAll('[data-export-dialog]').forEach(d=>d.remove());
    doc.querySelector('#payload').textContent=btoa(base);
    doc.querySelector('#content').innerHTML='<div class="empty">Loading scheduling workspace…</div>';
    doc.querySelector('#notice').textContent='';
    let dialog=doc.querySelector('#emailDialog');
    dialog.innerHTML='';
    dialog.removeAttribute('open');
    for(let id of ['tradeDialog','scheduleImportDialog','profileDialog','timeOffDialog','timeOffWorkbookDialog']){
        let d=doc.querySelector('#'+id);
        d.innerHTML='';
        d.removeAttribute('open')
    }
    return new Blob(['<!doctype html>\n'+doc.outerHTML],{
        type:'text/html'
    }
    )
}
async function portableBundleFiles(){
    await authorizeDataSettings('portable');
    if(location.protocol==='file:')throw Error('Portable bundle export requires a hosted app. Browsers block access to local CSS and JavaScript files.');
    let names=['CBL-Scheduler2.css','CBL-Scheduler2.js','CBL-Scheduler2.config.js','CBL-MicrosoftAuth.html'],assets=await Promise.all(names.map(async name=>{
        let response=await fetch(new URL(name,document.baseURI));
        if(!response.ok)throw Error('Unable to load '+name+' for export (HTTP '+response.status+').');
        return response.text()
    }
    )),html=await portableHtmlBlob();
    return {
        ...Object.fromEntries(names.map((name,index)=>[name,assets[index]])),
        'CBL-Scheduling-Command-Centre.html':await html.text()
    }
}
async function portable(){
    downloadFile('CBL-Scheduling-Command-Centre.zip',zipStore(await portableBundleFiles(),'application/zip'));
    message('Portable ZIP bundle prepared with this configuration and saved schedules. Extract all files before opening the included HTML.')
}
function embeddedDownloadContext(){
    try{
        return window.self!==window.top
    }
    catch{
        return true
    }

}
function downloadFile(name,blob){

     let url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;
    a.download=name;
    a.style.display='none';
    document.body.appendChild(a);

     if(!embeddedDownloadContext()){
        try{
            a.click()
        }
        finally{
            a.remove();
            setTimeout(()=>URL.revokeObjectURL(url),60000)
        }
        return
    }

     a.remove();
    let dlg=document.createElement('dialog');
    dlg.dataset.exportDialog='true';

     dlg.innerHTML=`<div class="dialoghead"><div><div class="eyebrow">EXPORT READY</div><h2>Save your file</h2></div><button type="button" data-export-close aria-label="Close">✕</button></div><p><b>${esc(name)}</b> · ${Math.ceil(blob.size/1024)} KB</p><p>This app is running inside an embedded viewer. SharePoint or your browser may block file downloads here.</p><div class="actions"><a class="primary" data-export-link>Download file</a><button type="button" data-export-save>Save as…</button></div><p data-export-status role="status">Click Download file, then check your browser’s downloads.</p><div class="callout">If nothing downloads, open the app outside the SharePoint preview. Use the SharePoint library’s Download command for the HTML file, open it from your computer, and generate or upload your schedules there. For team use entirely online, the app needs approved web hosting or a SharePoint app deployment that permits downloads. This file cannot override SharePoint’s restrictions.</div><p>Keep this workspace open until your file is saved. Changes may be session-only in the SharePoint viewer.</p>`;

     let link=dlg.querySelector('[data-export-link]');
    link.href=url;
    link.download=name;

     let save=dlg.querySelector('[data-export-save]'),status=dlg.querySelector('[data-export-status]');
    save.hidden=typeof window.showSaveFilePicker!=='function';

     save.onclick=async()=>{
        let handle;
        try{
            handle=await window.showSaveFilePicker({
                suggestedName:name
            }
            )
        }
        catch(err){
            status.textContent=err.name==='AbortError'?'Save cancelled. Your file is still ready.':'Save as is blocked in this viewer. Try Download file or open the app outside the SharePoint preview.';
            return
        }
        try{
            let stream=await handle.createWritable();
            await stream.write(blob);
            await stream.close();
            status.textContent='File saved: '+name
        }
        catch(err){
            status.textContent='File could not be saved: '+err.message
        }

    }
    ;

     dlg.querySelector('[data-export-close]').onclick=()=>dlg.close();
    dlg.addEventListener('close',()=>{
        URL.revokeObjectURL(url);dlg.remove()
    }
    ,{
        once:true
    }
    );
    document.body.appendChild(dlg);
    dlg.showModal();


}
$('sourceUpload').onchange=importSource;
$('restoreUpload').onchange=restoreWorkspace;
$('themeButton').onclick=()=>{
    model.theme=model.theme==='dark'?'light':'dark';
    render();
    queueSave()
}
;
async function init(){
    try{
        let encoded=atob($('payload').textContent.trim()),data=JSON.parse(new TextDecoder().decode(await inflate(Uint8Array.from(encoded,c=>c.charCodeAt(0)),'gzip')));
        model=migrateScheduleWeeks(data);
        try{
            let saved=await store('get');
            storageMode='persistent';
            if(saved)model=migrateScheduleWeeks(saved);
            else{
                model.roster=[];
                model.locations=[];
                model.pools=[];
                model.results=[];
                model.selectedRun='';
                model.controls.location='';
                model.controls.role='';
                model.locked=false;
            }
            storageStatus()
        }
        catch(e){
            storageMode='session';
            storageReason=e.message;
            storageStatus()
        }
        try{
            let sharedTheme=localStorage.getItem('cbl-application-theme');
            if(['light','dark'].includes(sharedTheme))model.theme=sharedTheme;
        }
        catch(error){console.warn('Unable to restore application theme:',error);}
        await loadBusinessConfig();
        await clearLegacyBambooCredentials();
        await loadAcceptedSchedules();
        await loadDirectoryData();
        await loadBambooPublishStatus();
        let authResponse=await fetch('/api/tenant-auth/state'),authState=await authResponse.json();
        if(!authResponse.ok||!authState.authenticated)throw Error(authState.error||'Your administrator session has expired.');
        tenantAuthCsrfToken=authState.csrfToken;
        tenantAuthTenantId=authState.tenantId;
        tenantAuthPrimaryAdmin=authState.isPrimaryAdmin===true;
        tenantMembership=authState.membership;
        await loadSharedRosterSettings();
        await loadSharedMetaSettings();
        model.user={firstName:authState.displayName||'',email:authState.email||''};
        try{
            await loadAttendanceData()
        }
        catch(error){
            attendanceSyncStatus=error.message
        }
        render();
        startAttendancePolling();
        startNotificationPolling();
    }
    catch(err){
        $('content').innerHTML='<div class="empty">Unable to open workspace: '+esc(err.message)+'</div>'
    }

}
if(!globalThis.TEST_MODE){
    if(typeof globalThis.CBL_STORAGE_BRIDGE==='function')globalThis.CBL_STORAGE_BRIDGE();
    init().finally(initHeaderCollapse)
}
else initHeaderCollapse();
