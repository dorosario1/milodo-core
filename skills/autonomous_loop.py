from skills.audit_engine import audit_html
from skills.patch_generator import generate_patched_html
from skills.orchestrator import run_orchestrator


def run_autonomous_loop(
    original_html: str,
    max_iterations: int = 5,
    convergence_threshold: float = 0.5,
    verbose: bool = True,
) -> dict:
    audit_result = audit_html(original_html)
    current_html = original_html
    previous_score = audit_result["score"]
    initial_score = previous_score
    iterations = []
    converged = False
    rollback_triggered = False
    max_iterations_reached = False

    for iteration in range(1, max_iterations + 1):
        patched_html = generate_patched_html(
            current_html,
            audit_result,
        )

        result = run_orchestrator(
            current_html,
            patched_html,
            audit_result,
            workspace_name=f"loop_{iteration}",
        )

        score_before = result.get("score_before")
        score_after = result.get("score_after")
        score_delta = result.get("score_delta")
        accepted = result.get("accepted", False)
        rollback_required = result.get("rollback_required", False)

        iterations.append({
            "iteration": iteration,
            "score_before": score_before,
            "score_after": score_after,
            "delta": score_delta,
            "accepted": accepted,
            "rollback_required": rollback_required,
            "workspace_name": f"loop_{iteration}",
        })

        if verbose:
            print(f"[LOOP] Iteration {iteration}")
            print(f"[LOOP] Score before: {score_before}")
            print(f"[LOOP] Score after: {score_after}")
            print(f"[LOOP] Delta: {score_delta}")
            print("[LOOP] Accepted" if accepted else "[LOOP] Rejected")

        if rollback_required:
            rollback_triggered = True
            if verbose:
                print("[LOOP] Rollback triggered")
            break

        delta_value = score_delta if score_delta is not None else 0.0
        if abs(delta_value) <= convergence_threshold:
            converged = True
            if verbose:
                print("[LOOP] Converged")
            break

        if score_after is not None and score_after >= 100:
            converged = True
            if verbose:
                print("[LOOP] Perfect score reached")
            break

        if accepted:
            current_html = patched_html
            previous_score = score_after
            audit_result = audit_html(current_html)

        if iteration == max_iterations:
            max_iterations_reached = True
            if verbose:
                print("[LOOP] Max iterations reached")

    final_audit = audit_html(current_html)
    final_score = final_audit["score"]

    return {
        "final_html": current_html,
        "final_score": final_score,
        "initial_score": initial_score,
        "improvement": round(final_score - initial_score, 2),
        "iterations": iterations,
        "iterations_count": len(iterations),
        "converged": converged,
        "rollback_triggered": rollback_triggered,
        "max_iterations_reached": max_iterations_reached,
    }
