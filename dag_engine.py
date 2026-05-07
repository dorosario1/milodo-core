from logger import log_info, log_error, log_warn, log_debug


class Task:
    def __init__(self, id, action, dependencies=None):
        self.id = str(id)
        self.action = action
        self.dependencies = list(dependencies or [])
        self.status = "pending"
        self.result = None


class DAGEngine:
    def __init__(self):
        self.tasks = {}
        self.execution_order = []
        self.errors = []

    def add_task(self, task):
        log_debug(f"Ajout tache: {task.id}")

        if task.id in self.tasks:
            error = f"Tache deja existante: {task.id}"
            log_warn(error)
            self.errors.append(error)
            return False

        self.tasks[task.id] = task
        return True

    def validate(self):
        log_debug("Validation DAG")
        self.errors = []

        self._validate_dependencies()
        self._detect_cycles()

        valid = len(self.errors) == 0
        log_debug(f"Validation terminee: {valid}")
        return valid

    def run(self):
        log_info(f"DAG démarré : {len(self.tasks)} tâches")

        if not self.validate():
            log_warn("Execution stoppee: DAG invalide")
            return self.get_status()

        pending = set(self.tasks.keys())
        completed = set()
        self.execution_order = []

        while pending:
            log_debug(f"Tâches restantes : {len(pending)}")
            ready_tasks = [
                task_id for task_id in pending
                if all(dep in completed for dep in self.tasks[task_id].dependencies)
            ]

            if not ready_tasks:
                error = "Execution stoppee: aucune tache executable"
                log_warn(error)
                self.errors.append(error)
                break

            for task_id in sorted(ready_tasks):
                task = self.tasks[task_id]
                task.status = "running"
                log_debug(f"Exécution tâche : {task.id}")

                try:
                    task.result = task.action()
                    task.status = "success"
                    completed.add(task_id)
                    pending.remove(task_id)
                    self.execution_order.append(task_id)
                    log_info(f"Tâche terminée : {task.id}")
                except Exception as error:
                    task.status = "failed"
                    task.result = str(error)
                    self.errors.append(f"Tache echouee {task.id}: {error}")
                    log_error(f"Tâche échouée : {task.id} - {error}")
                    return self.get_status()

        log_info("DAG terminé")
        return self.get_status()

    def get_status(self):
        return {
            "success": len(self.errors) == 0 and all(
                task.status == "success" for task in self.tasks.values()
            ),
            "tasks": {
                task_id: {
                    "id": task.id,
                    "dependencies": task.dependencies,
                    "status": task.status,
                    "result": task.result,
                }
                for task_id, task in self.tasks.items()
            },
            "execution_order": self.execution_order,
            "errors": self.errors,
        }

    def _validate_dependencies(self):
        for task in self.tasks.values():
            for dependency in task.dependencies:
                if dependency not in self.tasks:
                    error = f"Dependance manquante pour {task.id}: {dependency}"
                    log_warn(f"Dépendance manquante : {dependency}")
                    self.errors.append(error)

    def _detect_cycles(self):
        visited = set()
        visiting = set()

        for task_id in self.tasks:
            if task_id not in visited:
                self._visit(task_id, visited, visiting)

    def _visit(self, task_id, visited, visiting):
        if task_id in visiting:
            error = f"Cycle detecte: {task_id}"
            log_warn(error)
            self.errors.append(error)
            return

        if task_id in visited:
            return

        visiting.add(task_id)

        task = self.tasks.get(task_id)
        if task:
            for dependency in task.dependencies:
                if dependency in self.tasks:
                    self._visit(dependency, visited, visiting)

        visiting.remove(task_id)
        visited.add(task_id)
