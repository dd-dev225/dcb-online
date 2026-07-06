// Tri au clic sur l'en-tête, pour toute table marquée "table-sortable" : pas de
// rechargement de page, le tri se fait sur les lignes déjà présentes dans le
// tableau (tables sans pagination serveur, cf. dashboards/templates/.../*.html).
(function () {
    function texteCellule(cell) {
        return cell.textContent.trim();
    }

    function valeurComparable(texte) {
        var nombre = texte.replace(/\s/g, "").replace(",", ".");
        if (nombre !== "" && !isNaN(nombre)) {
            return parseFloat(nombre);
        }
        return texte.toLowerCase();
    }

    function trierTable(table, indexColonne, croissant) {
        var tbody = table.tBodies[0];
        var lignes = Array.prototype.slice.call(tbody.rows);
        // Une seule ligne avec colspan = ligne "Aucun ..." vide, rien à trier.
        if (lignes.length <= 1 && lignes[0] && lignes[0].cells.length === 1) {
            return;
        }
        lignes.sort(function (a, b) {
            var va = valeurComparable(texteCellule(a.cells[indexColonne]));
            var vb = valeurComparable(texteCellule(b.cells[indexColonne]));
            if (va < vb) return croissant ? -1 : 1;
            if (va > vb) return croissant ? 1 : -1;
            return 0;
        });
        lignes.forEach(function (ligne) {
            tbody.appendChild(ligne);
        });
    }

    function initTable(table) {
        var enTetes = table.tHead ? Array.prototype.slice.call(table.tHead.rows[0].cells) : [];
        enTetes.forEach(function (th, index) {
            if (th.dataset.noSort === "true" || th.textContent.trim() === "") {
                return;
            }
            th.classList.add("th-sortable");
            th.addEventListener("click", function () {
                var croissant = th.dataset.tri !== "asc";
                enTetes.forEach(function (autre) {
                    delete autre.dataset.tri;
                    autre.classList.remove("tri-asc", "tri-desc");
                });
                th.dataset.tri = croissant ? "asc" : "desc";
                th.classList.add(croissant ? "tri-asc" : "tri-desc");
                trierTable(table, index, croissant);
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("table.table-sortable").forEach(initTable);
    });
})();
