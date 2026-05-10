EXECUTION_PROFILES = {
    "safe": {
        "allowed": [
            "python",
            "git",
            "pip",
            "npm",
            "dir",
            "ls",
            "mkdir",
            "echo",
            "type",
            "cat",
            "node"
        ],
        "requires_confirmation": False,
        "description":
            "Commandes de développement sans risque"
    },

    "web": {
        "allowed": [
            "python",
            "curl",
            "wget"
        ],
        "requires_confirmation": False,
        "description":
            "Requêtes web, scraping, APIs"
    },

    "publish": {
        "allowed": [
            "git",
            "docker",
            "kubectl",
            "npm"
        ],
        "requires_confirmation": True,
        "description":
            "Déploiement, push, publication"
    },

    "full": {
        "allowed": ["*"],
        "requires_confirmation": True,
        "description":
            "Tout autorisé avec confirmation"
    }
}


DEFAULT_PROFILE = "safe"


def get_profile(
    profile_name
):
    """
    Retourne le profil demandé
    ou le profil par défaut.
    """

    return EXECUTION_PROFILES.get(
        profile_name,
        EXECUTION_PROFILES[
            DEFAULT_PROFILE
        ]
    )


def is_allowed(
    command,
    profile="safe"
):
    """
    Vérifie si une commande
    est autorisée.
    """

    p = get_profile(
        profile
    )

    if "*" in p["allowed"]:

        return (
            True,
            p["requires_confirmation"]
        )

    if isinstance(
        command,
        list
    ):

        if not command:

            return (
                False,
                p["requires_confirmation"]
            )

        cmd_base = str(
            command[0]
        ).strip().lower()

    else:

        command_str = str(
            command
        ).strip()

        if not command_str:

            return (
                False,
                p["requires_confirmation"]
            )

        cmd_base = (
            command_str
            .split()[0]
            .lower()
        )

    allowed = [
        cmd.lower()
        for cmd
        in p["allowed"]
    ]

    return (
        cmd_base in allowed,
        p["requires_confirmation"]
    )
