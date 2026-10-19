importScripts('vendor/jsqr/jsQR.js','phone_omr.js');
self.onmessage=({data})=>{
  try{
    const result=PhoneOMR.read(data.pixels,data.width,data.height,data.count,data.choices,jsQR);
    self.postMessage({result},[result.pixels.buffer]);
  }catch(error){self.postMessage({error:error.message});}
};
