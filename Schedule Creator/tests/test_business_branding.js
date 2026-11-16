function runBusinessBrandingTests(source) {
    new Function(source);
    const from=source.indexOf('function applyBranding('),to=source.indexOf('function businessSettingsPanel(',from);
    if(from<0||to<0)throw Error('Missing production branding test boundary');
    const fixture=document.createElement('div');
    fixture.innerHTML='<div class="brandblock"><img src="data:image/png;base64,AAAA" alt="CBL"></div><div class="workspace"><section class="hero"><div class="products"><img src="data:image/png;base64,BBBB" alt=""><img src="data:image/png;base64,CCCC" alt=""></div></section></div><div class="products"><img src="data:image/png;base64,DDDD" alt="Unrelated"></div>';
    document.body.append(fixture);
    const logo=fixture.querySelector('.brandblock img'),images=[...fixture.querySelectorAll('.hero .products img')];
    const defaults=[logo.src,...images.map(image=>image.src)];
    const unrelated=fixture.querySelector(':scope > .products img');
    const config={businessName:'Example business',supportingImages:[]};
    const apply=new Function('businessConfig','defaultBusinessLogos','defaultSupportingImages',
        source.slice(from,to)+';return applyBranding;')(config,new WeakMap(),new WeakMap());
    const originalTitle=document.title,originalBlue=document.documentElement.style.getPropertyValue('--blue'),
        originalGreen=document.documentElement.style.getPropertyValue('--green');
    let checks=0;
    const check=(value,label)=>{if(!value)throw Error(label);checks++;};
    try {
        apply();
        check(logo.src===defaults[0]&&images.every((image,index)=>image.src===defaults[index+1]),'Default artwork retained without saved images');
        config.logoDataUrl='data:image/png;base64,EEEE';
        apply();
        check(logo.src===config.logoDataUrl&&logo.alt===config.businessName,'Business logo replaces sidebar branding');
        check(images.every((image,index)=>image.src===defaults[index+1]),'Logo must not replace hero images');
        config.supportingImages=['data:image/png;base64,FFFF',''];
        apply();
        check(images[0].src===config.supportingImages[0]&&images[1].src===defaults[2],'Supporting image 1 replaces only the first hero slot');
        config.supportingImages=['','data:image/png;base64,GGGG'];
        apply();
        check(images[0].src===defaults[1]&&images[1].src===config.supportingImages[1],'Supporting image 2 preserves its slot when image 1 is absent');
        config.supportingImages=['data:image/png;base64,HHHH','data:image/png;base64,IIII'];
        apply();apply();
        check(images.every((image,index)=>image.src===config.supportingImages[index]),'Both supporting images survive repeated rendering');
        check(images[1].alt==='Example business supporting image 2','Supporting image label follows its slot');
        config.logoDataUrl='';config.supportingImages=[];
        apply();
        check(logo.src===defaults[0]&&images.every((image,index)=>image.src===defaults[index+1]&&image.alt===''),'Removal restores original artwork rather than the last custom image');
        check(unrelated.src==='data:image/png;base64,DDDD'&&unrelated.alt==='Unrelated','Unrelated product images remain unchanged');
        return {passed:checks};
    } finally {
        fixture.remove();
        document.title=originalTitle;
        for(const [name,value] of [['--blue',originalBlue],['--green',originalGreen]]){
            if(value)document.documentElement.style.setProperty(name,value);
            else document.documentElement.style.removeProperty(name);
        }

    }
}

async function runReportWorkbookBrandingTests(source) {
    const slice=(start,end)=>{const from=source.indexOf(start),to=source.indexOf(end,from);if(from<0||to<0)throw Error('Missing production test boundary: '+start);return source.slice(from,to);};
    const makeImage=format=>{
        const canvas=document.createElement('canvas');canvas.width=80;canvas.height=40;
        canvas.getContext('2d').fillRect(0,0,80,40);
        return canvas.toDataURL('image/'+format);
    };
    const saved={businessName:'=Example & Business',teamName:'Scheduling',logoDataUrl:makeImage('png'),
        supportingImages:[makeImage('jpeg'),makeImage('webp')]};
    let loaded={};
    const api=new Function('directoryRequest',
        slice('let businessConfig=','function applyBranding(')+
        slice('async function inflate(','function allScheduleRows(')+
        slice('function xml(','function exportTables(')+
        ';return {loadBusinessConfig,workbookBlob,parseXlsx,zipEntries,pending:image=>{businessConfig.logoDataUrl=image;businessConfig.supportingImages=[image];}};'
    )(async()=>({...loaded,supportingImages:[...(loaded.supportingImages||[])]}));
    let checks=0;
    const check=(condition,label)=>{if(!condition)throw Error(label);checks++;};
    const rows=[['Employee','Value'],['=Not a formula',12]];
    await api.loadBusinessConfig();
    const plain=await api.workbookBlob({'Weekly Schedules':rows});
    let parsed=await api.parseXlsx(await plain.arrayBuffer());
    check(JSON.stringify(parsed)===JSON.stringify({'Weekly Schedules':rows}),'Unbranded export preserves data and has no cover');
    loaded=saved;await api.loadBusinessConfig();
    api.pending(makeImage('png'));
    const branded=await api.workbookBlob({'Weekly Schedules':rows});
    parsed=await api.parseXlsx(await branded.arrayBuffer());
    check(Object.keys(parsed)[0]==='Business branding','Branded cover is the first sheet');
    check(JSON.stringify(parsed['Weekly Schedules'])===JSON.stringify(rows),'Original schedule remains importable without changed values');
    check(parsed['Business branding'][0][0]===saved.businessName,'Business name remains string data, not a formula');
    const archive=await api.zipEntries(await branded.arrayBuffer());
    check(archive.has('xl/media/business-branding-1.png')&&archive.has('xl/media/business-branding-2.jpeg')&&archive.has('xl/media/business-branding-3.png'),'PNG, JPEG and converted WebP are embedded');
    const parse=text=>new DOMParser().parseFromString(text,'application/xml');
    const drawing=parse(await archive.text('xl/drawings/business-branding.xml'));
    const xdr='http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing';
    check(drawing.getElementsByTagNameNS(xdr,'oneCellAnchor').length===3,'All saved images survive pending edits');
    check([...drawing.getElementsByTagNameNS(xdr,'ext')].every(ext=>Math.abs(Number(ext.getAttribute('cx'))/Number(ext.getAttribute('cy'))-2)<.001),'Image proportions are preserved');
    const data=parse(await archive.text('xl/worksheets/sheet1.xml'));
    check(!data.getElementsByTagNameNS('*','f').length,'Formula-looking text never becomes a formula');
    loaded={supportingImages:['',saved.supportingImages[1]]};await api.loadBusinessConfig();
    const second=await api.zipEntries(await (await api.workbookBlob({Attendance:rows})).arrayBuffer());
    const secondDrawing=parse(await second.text('xl/drawings/business-branding.xml'));
    check(secondDrawing.getElementsByTagNameNS(xdr,'col')[0].textContent==='5','Supporting image 2 retains its cover slot');
    loaded={logoDataUrl:'data:image/png;base64,AAAA'};await api.loadBusinessConfig();
    let rejected=false;
    try{await api.workbookBlob({Attendance:rows});}catch(error){rejected=error.message.includes('cannot be rendered');}
    check(rejected,'Invalid saved image rejects the export instead of silently omitting branding');
    return {passed:checks};
}

function runSupportingReportBrandingTests(snapshotHtml,historicalHtml) {
    let checks=0;
    for(const [html,start,end] of [
        [snapshotHtml,'const imagePattern=','document.title='],
        [historicalHtml,'const supportingPattern=','const detailSections=']
    ]){
        const from=html.indexOf(start),to=html.indexOf(end,from);
        if(from<0||to<0)throw Error('Missing report image rendering test boundary');
        const render=new Function('$','data',html.slice(from,to)),container=document.createElement('div');
        render(()=>container,{businessName:'Example',supportingImages:['','data:image/png;base64,AAAA']});
        if(container.children.length!==1||container.firstChild.alt!=='Example supporting image 2')throw Error('Supporting image 2 must render without requiring image 1');
        checks++;
        let rejected=false;
        try{render(()=>container,{businessName:'Example',supportingImages:[null]});}catch(error){rejected=error.message.includes('invalid');}
        if(!rejected)throw Error('Invalid nonempty report images must still fail explicitly');
        checks++;
    }
    return {passed:checks};
}
