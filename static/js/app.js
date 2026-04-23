const healthBtn = document.getElementById("healthBtn");
const output = document.getElementById("output");

healthBtn.addEventListener("click", async () => {
  output.textContent = "Checking...";

  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    output.textContent = `Error: ${error.message}`;
  }
});
