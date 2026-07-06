// Les dashboards (django-plotly-dash) sont affichés dans un <iframe> à hauteur
// fixe (paramètre height="...px" de {% plotly_app %}). Deviner cette hauteur en
// dur ne tient pas : le contenu réel grandit avec le temps (plus de mois de CA
// affichés, libellés qui changent de largeur...), et un wrapper trop petit fait
// apparaître la barre de défilement INTERNE de l'iframe (retour utilisateur
// répété). On mesure donc la hauteur réelle du document chargé DANS l'iframe et on
// l'applique au wrapper, sans jamais coder une valeur en pixels nous-mêmes.
// Même origine (django_plotly_dash servi par le même Django), donc
// iframe.contentWindow.document est accessible sans restriction cross-origin.
(function () {
    var MARGE_SECURITE_PX = 12;

    function ajusterHauteur(iframe) {
        try {
            var doc = iframe.contentWindow.document;
            var hauteur = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
            if (hauteur > 0) {
                iframe.parentElement.style.height = (hauteur + MARGE_SECURITE_PX) + "px";
            }
        } catch (e) {
            // Cross-origin ou iframe pas encore chargée : on retentera au prochain tick.
        }
    }

    function surveillerIframe(iframe) {
        ajusterHauteur(iframe);
        iframe.addEventListener("load", function () {
            ajusterHauteur(iframe);
            // Le contenu Dash se construit après le chargement de l'iframe
            // elle-même (callback expanded_callback asynchrone), donc un seul
            // ajustement au "load" arrive souvent trop tôt.
            setTimeout(function () { ajusterHauteur(iframe); }, 600);
            setTimeout(function () { ajusterHauteur(iframe); }, 1500);
        });
        // Filtre/changement de période dans le dashboard = nouveau contenu, donc
        // nouvelle hauteur, sans rechargement de l'iframe : on revérifie en continu.
        setInterval(function () { ajusterHauteur(iframe); }, 2000);
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll('iframe[src*="/django_plotly_dash/app/"]').forEach(surveillerIframe);
    });
})();
