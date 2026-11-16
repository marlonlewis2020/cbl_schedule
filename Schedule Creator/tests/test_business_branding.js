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
