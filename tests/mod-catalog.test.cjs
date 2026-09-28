const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {loadCatalog}=require('../core/mod-catalog.cjs');

function writeMod(root,id,extra={}){
  const dir=path.join(root,id);
  fs.mkdirSync(path.join(dir,'web'),{recursive:true});
  fs.writeFileSync(path.join(dir,'mod.json'),JSON.stringify({id,name:extra.name||id,priority:extra.priority,web:extra.web||['adapter.js'],electronMain:extra.electronMain,electronPreload:extra.electronPreload,enabled:extra.enabled,hwmod:extra.hwmod}));
  fs.writeFileSync(path.join(dir,'web','adapter.js'),'');
}

test('catalog loads enabled mods and skips unsafe ids or paths',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'hw-mods-'));
  writeMod(root,'alpha',{priority:20,web:['config.js','adapter.js']});
  writeMod(root,'beta',{priority:10,electronMain:'electron/main.cjs',electronPreload:'../escape.js'});
  writeMod(root,'off',{enabled:false});
  fs.mkdirSync(path.join(root,'not-a-mod'));
  fs.mkdirSync(path.join(root,'Bad Id'));
  fs.writeFileSync(path.join(root,'Bad Id','mod.json'),JSON.stringify({id:'Bad Id',web:['x.js']}));
  const catalog=loadCatalog(root);
  assert.deepEqual(catalog.map(m=>m.id),['beta','alpha']);
  assert.deepEqual(catalog[1].web,['config.js','adapter.js']);
  assert.equal(catalog[0].electronMain,'electron/main.cjs');
  assert.equal(catalog[0].electronPreload,null);
  assert.equal(catalog[0].hasAssets,false);
  fs.mkdirSync(path.join(root,'alpha','assets','animate'),{recursive:true});
  fs.writeFileSync(path.join(root,'alpha','assets','animate','character9.png'),'');
  const withAssets=loadCatalog(root);
  assert.equal(withAssets.find((mod)=>mod.id==='alpha').hasAssets,true);
});

test('catalog stores optional hwmod and loads the hello example',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'hw-mods-'));
  writeMod(root,'hello-hw-mod',{hwmod:'1',web:['main.js'],priority:50});
  const catalog=loadCatalog(root);
  assert.equal(catalog[0].hwmod,'1');
  const example=path.join(__dirname,'..','examples','hello-hw-mod');
  const fromExample=loadCatalog(path.dirname(example)).find((mod)=>mod.id==='hello-hw-mod');
  assert.equal(fromExample.hwmod,'1');
  assert.deepEqual(fromExample.web,['main.js']);
});
