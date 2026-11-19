const industryPicker = document.querySelector(".industry-picker");
const industryButtons = [...industryPicker.querySelectorAll("button")];

function showIndustry(selected) {
    for (const button of industryButtons) {
        const active = button === selected;
        button.setAttribute("aria-pressed", String(active));
        document.getElementById(button.getAttribute("aria-controls")).hidden = !active;
    }
}

for (const button of industryButtons) {
    button.addEventListener("click", () => showIndustry(button));
}
showIndustry(industryButtons[0]);
industryPicker.hidden = false;
