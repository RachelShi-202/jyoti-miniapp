'use strict';
const assert=require('assert');
const fs=require('fs');
const vm=require('vm');

class TextNode{
 constructor(text){this.nodeType=3;this.data=String(text)}
 get textContent(){return this.data}
}

class Element{
 constructor(tag){
  this.nodeType=1;this.tagName=tag.toUpperCase();this.children=[];this.id='';this.className='';this.scope='';this.nextElementSibling=null;
  this.classList={contains:name=>this.className.split(/\s+/).includes(name),add(){},remove(){},toggle(){}};
 }
 append(...items){this.children.push(...items)}
 after(){}
 replaceChildren(...items){this.children=[...items]}
 setAttribute(){}
 scrollIntoView(){}
 querySelector(){return null}
 get textContent(){return this.children.map(child=>child.textContent).join('')}
 set textContent(value){this.children=[new TextNode(value)]}
}

const document={createElement:tag=>new Element(tag),createTextNode:text=>new TextNode(text)};
const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element};
const source=fs.readFileSync(require('path').join(__dirname,'../static/app.js'),'utf8');
const renderer=source.slice(source.indexOf('function inlineText'),source.indexOf('let planSequence'));
assert(!renderer.includes('innerHTML'));
const context={document,node};vm.createContext(context);vm.runInContext(renderer,context);
const find=(root,tag,result=[])=>{if(root.tagName===tag)result.push(root);for(const child of root.children||[])find(child,tag,result);return result};

let box=new Element('article');box.id='test-report';
context.renderReading(box,'## 旧本命报告\n\n| 行星 | 落座 | 宫位 |\n|---|---|---|\n| **木星** | <script>globalThis.pwned=true</script> | 第10宫 |\n\n- 历史列表\n历史段落');
assert.strictEqual(find(box,'TABLE').length,1);
assert.strictEqual(find(box,'THEAD').length,1);
assert.strictEqual(find(box,'TBODY').length,1);
assert.strictEqual(find(box,'STRONG').length,1);
assert.strictEqual(find(box,'SCRIPT').length,0);
assert.strictEqual(context.pwned,undefined);
assert(box.textContent.includes('<script>globalThis.pwned=true</script>'));
assert.strictEqual(find(box,'H3').length,1);
assert.strictEqual(find(box,'UL').length,1);
assert.strictEqual(find(box,'P').length,1);

box=new Element('article');box.id='invalid-table';
context.renderReading(box,'| 行星 | 落座 |\n| -- | --- |\n| 木星 | 巨蟹 |');
assert.strictEqual(find(box,'TABLE').length,0);
assert(box.textContent.includes('| -- | --- |'));
console.log('Markdown table DOM/security/legacy tests passed');
