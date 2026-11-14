(()=>{
    const section=location.pathname.split('/').pop(),params=new URLSearchParams(location.search);
    const workforce=section==='access'||(section==='trades'&&params.get('adminView')!=='1');
    const owner=section==='owner'||section==='hub'||(section==='billing'&&params.get('view')==='owner');
    let profile=null,timer=null;
    async function api(path,options={}){
        const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
        const data=await response.json();if(!response.ok)throw Error(data.error||'Application request failed.');return data
    }
    const link=(text,href)=>{const a=document.createElement('a');a.textContent=text;a.href=href;return a;};
    async function start(){
        const embedded=window.self!==window.top;
        if(embedded)return;
        let endpoint=owner?'/api/hub/application-state':workforce?'/api/access/application-state':'/api/application/state';
        try{profile=await api(endpoint);}
        catch(error){
            if(section==='trades'&&!params.has('view')&&!params.has('adminView')){
                try{profile=await api('/api/application/state');}catch{location.replace('/signin');return;}
            }else if(section==='help'){
                try{profile=await api('/api/access/application-state');}
                catch{location.replace('/signin?'+new URLSearchParams({experience:'admin',next:location.pathname+location.search}));return;}
            }else if(section==='hub'){return;}
            else{location.replace('/signin?'+new URLSearchParams({experience:owner?'owner':workforce?'workforce':'admin',next:location.pathname+location.search}));return;}
        }
        let nav=profile.role==='owner'?[['Business','/app/owner'],['Billing','/app/billing?view=owner']]:
            profile.role==='admin'?[['Scheduling','/'],['Trade approvals','/app/trades?adminView=1'],['Business','/app/business'],['Billing','/app/billing'],['Help & knowledge base','/app/help']]:
            [['My workspace','/app/access'],['Shift trades','/app/trades'+(params.get('view')==='employee'?'?view=employee':'')],['Help & knowledge base','/app/help']];
        if(profile.role==='admin'&&!profile.isPrimaryAdmin)nav=nav.filter(([,url])=>url!=='/app/billing');
        if(profile.role==='manager'&&profile.hasPersonalView){
            nav.push(['Personal view','/app/access?view=employee'],['Management view','/app/access']);
        }
        const existing=document.getElementById('appMenu');
        if(existing){
            const links=document.createElement('div');links.className='shell-admin-links';
            nav.slice(1).forEach(([title,url])=>links.append(link(title,url)));
            existing.append(links);return;
        }
        document.body.classList.add('unified-experience');
        let theme;
        try{theme=localStorage.getItem('cbl-application-theme')||localStorage.getItem('cbl-trade-theme');}
        catch(error){console.warn('Unable to restore theme:',error);}
        if(['light','dark'].includes(theme))document.documentElement.dataset.theme=theme;
        document.documentElement.style.setProperty('--blue',profile.primaryColor||'#159bd5');
        document.documentElement.style.setProperty('--green',profile.accentColor||'#74bf16');
        const sidebar=document.createElement('nav');sidebar.id='applicationSidebar';sidebar.setAttribute('aria-label','Application navigation');
        sidebar.dataset.role=profile.role;
        const brand=document.createElement('strong');brand.textContent=profile.businessName||'Scheduling Command Centre';sidebar.append(brand);
        if(profile.logoDataUrl){const img=document.createElement('img');img.src=profile.logoDataUrl;img.alt=brand.textContent;sidebar.prepend(img);}
        nav.forEach(([text,url])=>{const a=link(text,url);if(new URL(url,location.href).pathname===location.pathname&&new URL(url,location.href).search===location.search)a.setAttribute('aria-current','page');sidebar.append(a);});
        const header=document.createElement('header');header.id='applicationHeader';
        const name=document.createElement('span');name.textContent=`${profile.teamName||'Schedule Management'} · ${profile.name} · ${profile.role}`;
        const actions=document.createElement('div'),bell=document.createElement('button'),themeButton=document.createElement('button'),logout=document.createElement('button');
        bell.type=themeButton.type=logout.type='button';bell.textContent='Alerts';bell.setAttribute('aria-expanded','false');
        themeButton.textContent='Light / dark';logout.textContent='Sign out';actions.append(bell,themeButton,logout);header.append(name,actions);
        const alerts=document.createElement('section');alerts.id='applicationAlerts';alerts.hidden=true;alerts.setAttribute('aria-label','Your alerts');
        const status=document.createElement('p');status.setAttribute('role','status');
        document.body.prepend(sidebar,header,alerts);alerts.append(status);
        themeButton.onclick=()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=value;try{localStorage.setItem('cbl-application-theme',value);localStorage.setItem('cbl-trade-theme',value);}catch(error){status.textContent=error.message;}};
        bell.onclick=()=>{alerts.hidden=!alerts.hidden;bell.setAttribute('aria-expanded',String(!alerts.hidden));if(!alerts.hidden)void refresh();};
        document.addEventListener('keydown',event=>{if(event.key==='Escape'){alerts.hidden=true;bell.setAttribute('aria-expanded','false');bell.focus();}});
        logout.onclick=async()=>{try{
            const path=profile.role==='owner'?'/api/hub/owner/logout':profile.role==='admin'?'/api/tenant-auth/logout':'/api/access/logout';
            await api(path,{method:'POST',headers:{'X-CSRF-Token':profile.csrfToken},body:'{}'});location.assign('/signin');
        }catch(error){alerts.hidden=false;status.textContent=error.message;}};
        async function refresh(){
            try{
                const items=[];
                if(profile.role==='owner'){
                    const data=await api('/api/hub/businesses');
                    (data.businesses||[]).filter(b=>b.status==='pending').forEach(b=>items.push([`Registration pending: ${b.name}`,'/app/owner']));
                }else{
                    const prefix=profile.role==='admin'?'/api/attendance':'/api/access';
                    if(profile.role==='admin'||(profile.role==='manager'&&params.get('view')!=='employee')){
                        const data=await api(prefix+'/notifications');
                        (data.notifications||[]).filter(n=>!n.read).forEach(n=>items.push([n.message||n.reason||'Attendance update',profile.role==='admin'?'/':'/app/access']));
                    }
                    const state=await api((profile.role==='admin'?'/api/shift-trades':'/api/access/trades')+(params.get('view')==='employee'?'?view=employee':''));
                    (state.trades||[]).filter(t=>t.unread).forEach(t=>items.push([`Trade: ${t.state}`,`/app/trades?${profile.role==='admin'?'adminView=1&':params.get('view')==='employee'?'view=employee&':''}trade=${encodeURIComponent(t.id)}`]));
                }
                alerts.replaceChildren(status);status.textContent=items.length?'Open an update to review it; viewing is not approval.':'No unread alerts.';
                items.forEach(([text,url])=>alerts.append(link(text,url)));bell.textContent=`Alerts (${items.length})`;
            }catch(error){status.textContent='Alerts unavailable: '+error.message;bell.textContent='Alerts unavailable';}
        }
        await refresh();timer=setInterval(()=>{if(!document.hidden)void refresh();},30000);
        window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
    }
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void start(),{once:true});else void start();
})();
