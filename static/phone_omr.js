/* Local optical reader. Pixels stay on the device; no credentials or answer key here. */
(function(root){
  'use strict';
  function solve(a,b){
    for(let c=0;c<8;c++){
      let k=c;for(let r=c+1;r<8;r++)if(Math.abs(a[r][c])>Math.abs(a[k][c]))k=r;
      if(Math.abs(a[k][c])<1e-8)throw Error('Sayfayı düz tutup yeniden çekin.');
      [a[c],a[k]]=[a[k],a[c]];[b[c],b[k]]=[b[k],b[c]];
      const v=a[c][c];for(let j=c;j<8;j++)a[c][j]/=v;b[c]/=v;
      for(let r=0;r<8;r++)if(r!==c){const f=a[r][c];for(let j=c;j<8;j++)a[r][j]-=f*a[c][j];b[r]-=f*b[c];}
    }return b;
  }
  function transform(points){
    const target=[[13,13],[197,13],[197,284],[13,284]],a=[],b=[];
    target.forEach(([x,y],i)=>{const [u,v]=points[i];a.push([x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]);b.push(u,v);});
    return solve(a,b);
  }
  function markers(gray,w,h){
    const seen=new Uint8Array(w*h),queue=new Int32Array(w*h),found=[];
    for(let start=0;start<gray.length;start++){
      if(seen[start]||gray[start]>=110)continue;
      let head=0,tail=1,minX=w,minY=h,maxX=0,maxY=0;queue[0]=start;seen[start]=1;
      while(head<tail){
        const p=queue[head++],x=p%w,y=(p/w)|0;
        minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
        for(const n of [x? p-1:-1,x<w-1?p+1:-1,y?p-w:-1,y<h-1?p+w:-1]){
          if(n>=0&&!seen[n]&&gray[n]<110){seen[n]=1;queue[tail++]=n;}
        }
      }
      const bw=maxX-minX+1,bh=maxY-minY+1,area=bw*bh;
      if(tail>90&&bw>14&&bh>14&&bw<w*.15&&bh<h*.15&&bw/bh>.55&&bw/bh<1.8&&tail/area>.3)
        found.push({x:(minX+maxX)/2,y:(minY+maxY)/2,area});
    }
    const corners=[];
    for(let q=0;q<4;q++){
      const right=q===1||q===2,bottom=q>=2;
      const candidates=found.filter(p=>(p.x>w/2)===right&&(p.y>h/2)===bottom).sort((a,b)=>((right?w-a.x:a.x)/w+(bottom?h-a.y:a.y)/h)-((right?w-b.x:b.x)/w+(bottom?h-b.y:b.y)/h));
      if(!candidates.length)throw Error('Dört köşe görünmüyor. Optiği kadraja alın ve telefonu dik tutun.');
      corners.push(candidates[0]);
    }
    const sizes=corners.map(p=>p.area);
    if(Math.max(...sizes)>Math.min(...sizes)*2.5)throw Error('Optiği düzleştirin; dört köşe eşit netlikte görünmeli.');
    const area=Math.abs(corners.reduce((s,p,i)=>{const n=corners[(i+1)%4];return s+p.x*n.y-p.y*n.x;},0))/2;
    if(area<w*h*.25)throw Error('Optik çok uzakta. Sayfanın tamamı görünürken biraz yaklaşın.');
    return corners.map(p=>[p.x,p.y]);
  }
  function read(pixels,w,h,count,choices,qr){
    const gray=new Uint8Array(w*h);
    for(let i=0;i<gray.length;i++)gray[i]=(pixels[4*i]*77+pixels[4*i+1]*150+pixels[4*i+2]*29)>>8;
    const points=markers(gray,w,h),W=840,H=1188;
    let normalized,code;
    for(let turn=0;turn<4;turn++){
      const m=transform(points.slice(turn).concat(points.slice(0,turn)));
      normalized=new Uint8ClampedArray(W*H*4);
      for(let y=0;y<H;y++)for(let x=0;x<W;x++){
        const X=x/4,Y=y/4,d=m[6]*X+m[7]*Y+1;
        const u=Math.round((m[0]*X+m[1]*Y+m[2])/d),v=Math.round((m[3]*X+m[4]*Y+m[5])/d);
        const c=u>=0&&u<w&&v>=0&&v<h?gray[v*w+u]:255,i=(y*W+x)*4;
        normalized[i]=normalized[i+1]=normalized[i+2]=c;normalized[i+3]=255;
      }
      const rw=176,rh=168,roi=new Uint8ClampedArray(rw*rh*4);
      for(let y=0;y<rh;y++)roi.set(normalized.subarray(((y+68)*W+624)*4,((y+68)*W+624+rw)*4),y*rw*4);
      code=qr(roi,rw,rh,{inversionAttempts:'dontInvert'});
      if(code&&code.data.startsWith('AP2:'))break;
      if(code&&code.data.startsWith('AP1:'))throw Error('Eski optik için sunucuda okuma kullanılıyor.');
    }
    if(!code||!code.data.startsWith('AP2:'))throw Error('QR okunamadı. Işığı artırıp sayfayı düz tutun.');
    const answers=[],uncertain=[],rows=count<=60?20:30;
    for(let i=0;i<count;i++){
      const values=[];
      for(let j=0;j<choices.length;j++){
        const cx=(30+Math.floor(i/rows)*62+j*8)*4,cy=(72+(i%rows)*(rows===20?9:6.2))*4;
        let paper=0,np=0;
        for(let dy=-15;dy<=15;dy++)for(let dx=-15;dx<=15;dx++){
          const r=dx*dx+dy*dy;
          if(r>=169&&r<=225){paper+=normalized[(Math.round(cy+dy)*W+Math.round(cx+dx))*4];np++;}
        }
        const bg=paper/np,threshold=bg-Math.max(35,bg*.25);let dark=0,n=0;
        for(let dy=-6;dy<=6;dy++)for(let dx=-6;dx<=6;dx++)if(dx*dx+dy*dy<=36){
          if(normalized[(Math.round(cy+dy)*W+Math.round(cx+dx))*4]<threshold)dark++;n++;
        }
        values.push(bg<100?1:dark/n);
      }
      const ordered=[...values].sort((a,b)=>b-a);
      const answer=ordered[0]>.65&&ordered[1]<.12?choices[values.indexOf(ordered[0])]:'';
      answers.push(answer);if(!answer&&ordered[0]>.05)uncertain.push(i+1);
    }
    if(!answers.some(Boolean))for(let i=1;i<=count;i++)if(!uncertain.includes(i))uncertain.push(i);
    return {token:code.data.slice(4),answers,uncertain,pixels:normalized,width:W,height:H};
  }
  if(typeof module!=='undefined')module.exports={read};else root.PhoneOMR={read};
})(typeof self!=='undefined'?self:this);
