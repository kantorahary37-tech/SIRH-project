// Exemple de graphiques simples
const ctx1 = document.getElementById('chart1');
new Chart(ctx1, {
    type: 'bar',
    data: {
        labels: ['Actifs', 'Inactifs', 'Nouveaux', 'Retraite'],
        datasets: [{
            label: 'Effectif',
            data: [245, 37, 12, 9],
        }]
    }
});

const ctx2 = document.getElementById('chart2');
new Chart(ctx2, {
    type: 'pie',
    data: {
        labels: ['Hommes', 'Femmes'],
        datasets: [{
            data: [60, 40],
        }]
    }
});
