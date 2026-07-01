()=>{
  var out=[];
  document.querySelectorAll("select").forEach(function(s){
    var q="";
    var al=s.getAttribute("aria-label")||s.getAttribute("title")||"";
    if(al){q=al;}
    else if(s.id){
      var lb=document.querySelector("label[for='"+s.id+"']")||document.querySelector('label[for="'+s.id+'"]');
      if(lb){q=lb.textContent.trim();}
    }
    if(!q){
      var row=s.closest("tr");
      if(row){
        var cells=row.querySelectorAll("td,th");
        for(var i=0;i<cells.length;i++){
          if(!cells[i].contains(s)&&cells[i].textContent.trim().length>3){
            q=cells[i].textContent.trim().slice(0,100);break;
          }
        }
      }
    }
    var opts=[];
    for(var j=0;j<s.options.length;j++){opts.push(s.options[j].text.trim());}
    out.push({id:s.id||"",name:s.name||"",q:q.slice(0,150),opts:opts.slice(0,25),cur:s.value||""});
  });
  return out;
}
