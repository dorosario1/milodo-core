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
        print(f"Ajout tache: {task.id}")

        if task.id in self.tasks:
            error = f"Tache deja existante: {task.id}"
            print(error)
            self.errors.append(error)
            return False

        self.tasks[task.id] = task
        return True

    def validate(self):
        print("Validation DAG")
        self.errors = []

        self._validate_dependencies()
        self._detect_cycles()

        valid = len(self.errors) == 0
        print(f"Validation terminee: {valid}")
        return valid

    def run(self):
        print("Execution DAG")

        if not self.validate():
            print("Execution stoppee: DAG invalide")
            return self.get_status()

        pending = set(self.tasks.keys())
        completed = set()
        self.execution_order = []

        while pending:
            ready_tasks = [
                task_id for task_id in pending
                if all(dep in completed for dep in self.tasks[task_id].dependencies)
            ]

            if not ready_tasks:
                error = "Execution stoppee: aucune tache executable"
                print(error)
                self.errors.append(error)
                break

            for task_id in sorted(ready_tasks):
                task = self.tasks[task_id]
                task.status = "running"
                print(f"Execution tache: {task.id}")

                try:
                    task.result = task.action()
                    task.status = "success"
                    completed.add(task_id)
                    pending.remove(task_id)
                    self.execution_order.append(task_id)
                    print(f"Tache terminee: {task.id}")
                except Exception as error:
                    task.status = "failed"
                    task.result = str(error)
                    self.errors.append(f"Tache echouee {task.id}: {error}")
                    print(f"Tache echouee: {task.id} ({error})")
                    return self.get_status()

        print("Execution DAG terminee")
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
                    print(error)
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
            print(error)
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
