// ==========================================
// EDA Dashboard JavaScript
// ==========================================

document.addEventListener("DOMContentLoaded", function () {

    // -------------------------------
    // Search Functionality
    // -------------------------------

    const searchBox = document.getElementById("searchBox");
    const graphCards = document.querySelectorAll(".graph-card");

    if (searchBox) {

        searchBox.addEventListener("keyup", function () {

            const searchValue = searchBox.value.toLowerCase();

            graphCards.forEach(function (card) {

                const title = card.querySelector("h6").innerText.toLowerCase();

                if (title.includes(searchValue)) {

                    card.style.display = "block";

                } else {

                    card.style.display = "none";

                }

            });

        });

    }

    // -------------------------------
    // Image Click Preview
    // -------------------------------

    const images = document.querySelectorAll(".graph-image");

    images.forEach(function (image) {

        image.addEventListener("click", function () {

            window.open(image.src, "_blank");

        });

    });

    console.log("EDA Dashboard Loaded Successfully");

});