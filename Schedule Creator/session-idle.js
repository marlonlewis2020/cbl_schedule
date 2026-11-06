(()=>{
    'use strict';
    const originalFetch=window.fetch.bind(window);
    let clock=null,csrf='',expired=false,lastReport=-Infinity,inFlight=false,pendingActivity=null,banner=null;
    const loginPath=location.pathname.startsWith('/developer/')?'/developer/change-requests':location.pathname.startsWith('/app/')?'/signin':
        location.pathname==='/hub'||(location.pathname==='/billing'&&new URLSearchParams(location.search).get('view')==='owner')?'/hub':
        location.pathname==='/access'||(location.pathname==='/trades'&&!new URLSearchParams(location.search).has('adminView'))?'/access':'/';

    function expire(){
        if(expired)return;
        expired=true;
        clearInterval(timer);
        clock=null;
        document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
        document.body.replaceChildren();
        const notice=document.createElement('main');
        notice.setAttribute('role','alert');
        notice.style.cssText='padding:2rem;font:16px sans-serif';
        notice.textContent='Your session expired. Unsaved changes may not have been saved. Sign in again to continue. ';
        const link=document.createElement('a');
        link.href=loginPath;
        link.textContent='Sign in';
        notice.append(link);
        document.body.append(notice);
        // Navigation stops page-specific polling; existing beforeunload warnings still apply.
        location.replace(loginPath);
    }

    window.fetch=async(...args)=>{
        const input=args[0],url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
        if(expired&&url.origin===location.origin)throw Error('Session expired. Sign in again.');
        const response=await originalFetch(...args);
        if(expired&&url.origin===location.origin)throw Error('Session expired. Sign in again.');
        if(url.origin===location.origin&&url.pathname.startsWith('/api/')){
            if(response.status===401){
                const data=await response.clone().json().catch(()=>null);
                if(data?.sessionExpired)expire();
            }
            if(response.ok&&/\/(login|verify-mfa|setup|credentials)$/.test(url.pathname))void sync();
        }
        return response
    };

    function warning(){
        if(!clock||expired)return;
        const remaining=Math.ceil((clock.deadline-performance.now())/1000);
        if(remaining<=0){void sync();return;}
        if(remaining>60){banner?.remove();banner=null;return;}
        if(!banner){
            banner=document.createElement('aside');
            banner.setAttribute('role','alert');
            banner.style.cssText='position:fixed;bottom:16px;left:16px;right:16px;z-index:2147483647;padding:16px;border:2px solid #916000;background:#fff3cd;color:#302600;font:16px sans-serif;box-shadow:0 2px 12px #0005';
            const text=document.createElement('span'),button=document.createElement('button');
            button.type='button';
            button.textContent='Stay signed in';
            button.style.cssText='margin-left:16px;padding:8px';
            button.addEventListener('click',event=>{if(event.isTrusted)void report('continue');});
            banner.append(text,button);
            document.body.append(banner);
        }
        banner.firstChild.textContent=`Your session expires in ${remaining} seconds. Save any unsaved changes.`;
        banner.lastChild.hidden=clock.absolute;
    }

    async function sync(activity){
        if(expired)return;
        if(inFlight){if(activity)pendingActivity=activity;return;}
        inFlight=true;
        try{
            const response=await originalFetch('/api/session/state',{
                method:activity?'POST':'GET',cache:'no-store',
                headers:activity?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},
                ...(activity?{body:JSON.stringify({activity})}:{})
            });
            const data=await response.json();
            if(response.status===401){
                if(clock||data.sessionExpired)expire();
                return
            }
            if(!response.ok)throw Error(data.error||'Unable to verify your session.');
            csrf=data.csrfToken;
            const deadline=Math.min(data.idleExpiresAt,data.absoluteExpiresAt);
            clock={deadline:performance.now()+Math.max(0,deadline-data.serverTime)*1000,
                absolute:data.absoluteExpiresAt<=data.idleExpiresAt};
            warning();
        }
        catch(error){
            if(clock&&performance.now()>=clock.deadline){expire();return;}
            console.error('Session verification failed:',error);
            if(banner)banner.firstChild.textContent='Session verification failed. Save your work and check your connection.';
        }
        finally{
            inFlight=false;
            if(pendingActivity&&!expired){
                const activity=pendingActivity;
                pendingActivity=null;
                void sync(activity)
            }
        }
    }

    async function report(activity='interaction'){
        if(!clock||expired||document.visibilityState!=='visible')return;
        const now=performance.now();
        if(activity!=='continue'&&now-lastReport<30000)return;
        lastReport=now;
        await sync(activity);
    }
    for(const name of ['pointerdown','keydown','input','touchstart']){
        document.addEventListener(name,event=>{if(event.isTrusted)void report();},{capture:true,passive:true});
    }
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')void sync();});
    window.addEventListener('pageshow',()=>void sync());
    let tick=0;
    const timer=setInterval(()=>{warning();if(++tick%15===0)void sync();},1000);
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void sync(),{once:true});
    else void sync();
})();
