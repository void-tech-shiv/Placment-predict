const search = document.getElementById("searchReport");

if(search){

search.addEventListener("keyup",function(){

const value=this.value.toLowerCase();

const cards=document.querySelectorAll(".report-card");

cards.forEach(card=>{

card.style.display=

card.innerText.toLowerCase().includes(value)

? "block"

: "none";

});

});

}