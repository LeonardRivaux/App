const form = document.getElementById("missionForm");
const output = document.getElementById("output");
const missionsList = document.getElementById("missionsList");

async function loadMissions() {
  try {
    const response = await fetch("http://127.0.0.1:8000/missions");
    const data = await response.json();
    missionsList.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    missionsList.textContent = "Erreur : " + error.message;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const start = document.getElementById("start").value;
  const end = document.getElementById("end").value;

  const missionData = {
    start: start,
    end: end
  };

  try {
    const response = await fetch("http://127.0.0.1:8000/missions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(missionData)
    });

    const data = await response.json();
    output.textContent = JSON.stringify(data, null, 2);

    form.reset();
    loadMissions();
  } catch (error) {
    output.textContent = "Erreur : " + error.message;
  }
});

loadMissions();