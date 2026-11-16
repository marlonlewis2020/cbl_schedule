async function runIdleBrowserTests(source,interactive=false){
    new Function(source);
    let passed=0;
    const assert=(value,label)=>{if(!value)throw Error(label);passed++;};
    const flush=()=>new Promise(resolve=>setTimeout(resolve,20));
    async function fixture(path='/'){
        const frame=document.createElement('iframe');
        document.body.append(frame);
        const doc=frame.contentDocument;
        doc.body.innerHTML='<main id="protected">Protected content</main><input id="typing">';
        let now=0,idle=900,absolute=28800,authenticated=true,timer,stopped=false,navigated='',posts=0,gets=0,failure=false;
        const listeners={};
        const location={pathname:path,search:path==='/billing'?'?view=owner':'',href:'https://test.example'+path,origin:'https://test.example',replace:value=>{navigated=value;}};
        const fetch=async(url,options={})=>{
            if(failure)throw Error('Network unavailable');
            if(String(url)==='/api/session/state'){
                if(options.method==='POST')posts++;else gets++;
                if(!authenticated||now>=idle||now>=absolute)return new Response(JSON.stringify({sessionExpired:true}),{status:401});
                if(options.method==='POST')idle=now+900;
                return new Response(JSON.stringify({serverTime:now,idleExpiresAt:idle,absoluteExpiresAt:absolute,csrfToken:'test-token'}));
            }
            return new Response('{}');
        };
        const win={fetch,addEventListener:(name,handler)=>{listeners[name]=handler;}};
        const proxyDoc=new Proxy(doc,{get(target,key){
            if(key==='addEventListener')return (name,handler)=>{listeners[name]=handler;target.addEventListener(name,handler);};
            const value=Reflect.get(target,key,target);
            return typeof value==='function'?value.bind(target):value;
        }});
        new Function('window','document','location','performance','setInterval','clearInterval',
            source)(win,proxyDoc,location,{now:()=>now*1000},
            handler=>{timer=handler;return 1;},()=>{stopped=true;});
        await flush();
        return {doc,win,listeners,flush,
            tick:async(time)=>{now=time;timer();await flush();},
            state:()=>({posts,gets,stopped,navigated}),
            set:(values)=>{if('idle'in values)idle=values.idle;if('absolute'in values)absolute=values.absolute;if('failure'in values)failure=values.failure;},
            activity:async(trusted=true)=>{listeners.keydown({isTrusted:trusted});await flush();},
            dispose:()=>frame.remove()};
    }
    let f=await fixture();
    if(interactive){window.idleTestFixture=f;return {ready:true};}
    assert(f.state().gets>=1&&f.state().posts===0,'Startup checks session without renewing');
    await f.activity(false);
    assert(f.state().posts===0,'Synthetic events do not renew');
    await f.tick(840);
    assert(f.doc.querySelector('[role="alert"]').textContent.includes('60 seconds'),'Warning appears sixty seconds before deadline');
    await f.activity();
    assert(f.state().posts===1&&!f.doc.querySelector('[role="alert"]'),'Real interaction renews and dismisses warning');
    await f.activity();
    assert(f.state().posts===1,'Activity reports are throttled');
    await f.tick(900);
    assert(!f.state().stopped,'Renewed session remains usable');
    await f.tick(1740);
    assert(f.state().stopped&&f.state().navigated==='/','Expiry stops monitoring and returns to sign-in');
    assert(!f.doc.getElementById('protected'),'Expiry removes protected content');
    try{await f.win.fetch('/api/attendance');throw Error('Fetch should be blocked');}
    catch(error){assert(error.message.includes('Session expired'),'Authenticated polling blocked after expiry');}
    f.dispose();

    f=await fixture('/access');
    await f.tick(800);
    f.set({idle:1600});
    await f.listeners.visibilitychange();
    await f.flush();
    await f.tick(900);
    assert(!f.state().stopped,'Other-tab renewal observed without local activity');
    assert(f.state().posts===0,'Visibility refresh does not renew');
    await f.tick(1600);
    assert(f.state().navigated==='/access','Access expiry returns to Access sign-in');
    f.dispose();

    f=await fixture('/billing');
    f.set({absolute:850});
    await f.listeners.pageshow();
    await f.flush();
    await f.tick(800);
    assert(f.doc.querySelector('[role="alert"] button').hidden,'Absolute deadline cannot be extended from warning');
    await f.activity();
    await f.tick(850);
    assert(f.state().navigated==='/hub','Owner absolute expiry returns to Hub');
    f.dispose();

    f=await fixture('/developer/change-requests');
    f.set({failure:true});
    await f.tick(900);
    assert(f.state().stopped&&f.state().navigated==='/developer/change-requests','Expired offline session fails closed');
    f.dispose();
    return {passed};
}
