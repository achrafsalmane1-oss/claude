# Haven — de la reponse positive au rendez-vous pose

Pour les **campagnes a venir**, ou une reponse positive ne demande aucun
travail de notre part (pas de liste a construire).

    reponse positive        -> 3 creneaux reellement libres, proposes par email
    le prospect en accepte  -> on pose le rendez-vous sur Calendly a sa place
    refus / desabonnement   -> classe, aucune reponse
    absence du bureau       -> ignore (c'est un robot qui a repondu)
    tout le reste           -> silence, et un email a Achraf

Le prospect **ne recoit jamais de lien de reservation** : on ne lui demande que
de dire oui a une heure. C'est nous qui creons l'evenement.

## Ce qui ne part jamais tout seul

- `START_AFTER` est **obligatoire**. Aucun message anterieur a cette date n'est
  meme lu. Les fils en cours (Greg, Dave, Bob et les autres) sont hors de
  portee, definitivement.
- `BCC_TO` est obligatoire : sans copie cachee, le robot refuse d'envoyer.
- `MAX_SENDS` (3) envois automatiques par prospect, ensuite escalade.
- Jamais de reponse a un auto-repondeur.
- Un "oui" et l'acceptation d'un creneau doivent arriver dans **deux messages
  distincts** : le message qui declenche la proposition ne peut pas servir a
  poser le rendez-vous.
- Le creneau est **revalide** juste avant d'etre pose.
- Tout ce qui n'est pas franc part a l'humain et le robot se tait sur ce fil.
- `AUTOREPLY_ENABLED=0` coupe tout. `DRY_RUN=1` journalise sans rien envoyer.
- `audit.log` garde une ligne par decision.

## Le texte cite est coupe avant lecture

Une reponse contient presque toujours notre propre argumentaire en citation.
Le classer sans le couper fait lire « happy to build you a list, interested? »
comme la reponse du prospect. Teste sur les 80 reponses reelles de la boite
Haven : **avant correction, un « STOP » et un « 0.00% chance » etaient classes
positifs** et l'un aurait recu une invitation. Apres correction : zero faux
positif sur les 80.

## Mise en service

    export PLUSVIBE_API_KEY=...
    export CALENDLY_TOKEN=...              # plan payant, jeton personnel
    export CALENDLY_EVENT_SLUG=haven-intro
    export START_AFTER="$(cat haven_autoreply/START_AFTER)"
    export BCC_TO=achraf@havenstcapital.com
    export DRY_RUN=1                       # a garder pour les premiers passages
    python haven_autoreply/autoreply.py

`PV_WORKSPACE_ID` vise le workspace Haven. `CAMPAIGN_IDS` vide = toutes les
campagnes du workspace, futures comprises ; `SKIP_CAMPAIGN_IDS` en exclut
(une campagne ou la reponse demande un vrai travail, par exemple).

## Tests

    python haven_autoreply/test_classify.py     # 47 cas, dont 9 reponses reelles
