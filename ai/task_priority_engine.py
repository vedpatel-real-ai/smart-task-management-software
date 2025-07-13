from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

class TaskType(Enum):
    URGENT_IMPORTANT = "urgent_important"
    IMPORTANT_NOT_URGENT = "important_not_urgent"
    URGENT_NOT_IMPORTANT = "urgent_not_important"
    NEITHER = "neither"

class ImpactLevel(Enum):
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    MINIMAL = 1

@dataclass
class TaskContext:
    """Enhanced task context for advanced priority calculation"""
    dependencies: List[str] = None
    blockers: List[str] = None
    estimated_hours: float = 1.0
    actual_hours_spent: float = 0.0
    complexity_score: int = 3  # 1-5 scale
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    task_type: TaskType = TaskType.NEITHER
    is_blocking_others: bool = False
    team_size: int = 1
    creation_date: datetime = None
    last_updated: datetime = None
    postponement_count: int = 0
    energy_level_required: int = 3  # 1-5 scale (1=low energy, 5=high energy)

class calculate_priority_score:
    """Next-level task priority engine with advanced algorithms"""
    
    def __init__(self):
        self.priority_weights = {
            'deadline_urgency': 0.25,
            'manual_priority': 0.20,
            'impact_score': 0.20,
            'dependency_factor': 0.15,
            'complexity_adjustment': 0.10,
            'procrastination_penalty': 0.10
        }
        
        # Learning weights that can be adjusted based on user behavior
        self.adaptive_weights = {
            'user_completion_pattern': 1.0,
            'time_of_day_factor': 1.0,
            'energy_alignment': 1.0
        }
    
    def calculate_priority_score(self, task, context: TaskContext = None, 
                               current_time: datetime = None) -> Tuple[float, Dict]:
        """
        Calculate advanced priority score with detailed breakdown
        Returns: (score, breakdown_dict)
        """
        if task.completed:
            return 0.0, {"reason": "Task completed"}
        
        current_time = current_time or datetime.utcnow()
        context = context or TaskContext()
        
        # Initialize breakdown for transparency
        breakdown = {}
        
        # 1. Deadline Urgency (Enhanced)
        deadline_score = self._calculate_deadline_urgency(task, current_time)
        breakdown['deadline_urgency'] = deadline_score
        
        # 2. Manual Priority (Enhanced with context)
        manual_score = self._calculate_manual_priority(task, context)
        breakdown['manual_priority'] = manual_score
        
        # 3. Impact Score (New)
        impact_score = self._calculate_impact_score(task, context)
        breakdown['impact_score'] = impact_score
        
        # 4. Dependency Factor (New)
        dependency_score = self._calculate_dependency_factor(task, context)
        breakdown['dependency_factor'] = dependency_score
        
        # 5. Complexity Adjustment (New)
        complexity_score = self._calculate_complexity_adjustment(task, context)
        breakdown['complexity_adjustment'] = complexity_score
        
        # 6. Procrastination Penalty (New)
        procrastination_score = self._calculate_procrastination_penalty(task, context, current_time)
        breakdown['procrastination_penalty'] = procrastination_score
        
        # Calculate weighted base score
        base_score = (
            deadline_score * self.priority_weights['deadline_urgency'] +
            manual_score * self.priority_weights['manual_priority'] +
            impact_score * self.priority_weights['impact_score'] +
            dependency_score * self.priority_weights['dependency_factor'] +
            complexity_score * self.priority_weights['complexity_adjustment'] +
            procrastination_score * self.priority_weights['procrastination_penalty']
        )
        
        # Apply adaptive factors
        adaptive_multiplier = self._calculate_adaptive_multiplier(task, context, current_time)
        breakdown['adaptive_multiplier'] = adaptive_multiplier
        
        final_score = base_score * adaptive_multiplier
        
        # Apply boost for critical tasks
        if context.task_type == TaskType.URGENT_IMPORTANT:
            final_score *= 1.5
            breakdown['critical_boost'] = 1.5
        
        breakdown['base_score'] = base_score
        breakdown['final_score'] = round(final_score, 2)
        
        return round(final_score, 2), breakdown
    
    def _calculate_deadline_urgency(self, task, current_time: datetime) -> float:
        """Enhanced deadline urgency calculation"""
        if not hasattr(task, 'deadline') or not task.deadline:
            return 25.0  # Default moderate urgency for tasks without deadlines
        
        time_remaining = task.deadline - current_time
        hours_remaining = time_remaining.total_seconds() / 3600
        
        if hours_remaining < 0:
            # Overdue - exponential penalty
            overdue_hours = abs(hours_remaining)
            return min(100.0, 50.0 + (overdue_hours * 2))
        
        if hours_remaining < 1:
            return 95.0  # Due within an hour
        elif hours_remaining < 6:
            return 80.0  # Due within 6 hours
        elif hours_remaining < 24:
            return 60.0  # Due within a day
        elif hours_remaining < 72:
            return 40.0  # Due within 3 days
        elif hours_remaining < 168:  # 1 week
            return 25.0
        else:
            # Gradual decrease for longer deadlines
            days_remaining = hours_remaining / 24
            return max(5.0, 25.0 - (days_remaining * 0.5))
    
    def _calculate_manual_priority(self, task, context: TaskContext) -> float:
        """Enhanced manual priority with context"""
        base_priority = getattr(task, 'priority', 3) * 10  # 1-5 scale to 10-50
        
        # Adjust based on task type
        if context.task_type == TaskType.URGENT_IMPORTANT:
            base_priority *= 1.3
        elif context.task_type == TaskType.IMPORTANT_NOT_URGENT:
            base_priority *= 1.1
        elif context.task_type == TaskType.URGENT_NOT_IMPORTANT:
            base_priority *= 0.9
        
        return min(50.0, base_priority)
    
    def _calculate_impact_score(self, task, context: TaskContext) -> float:
        """Calculate impact score based on consequences"""
        impact_base = context.impact_level.value * 10  # 10-50 scale
        
        # Boost for tasks blocking others
        if context.is_blocking_others:
            impact_base *= 1.4
        
        # Adjust for team size (more people affected = higher impact)
        team_multiplier = 1.0 + (context.team_size - 1) * 0.1
        impact_base *= team_multiplier
        
        return min(50.0, impact_base)
    
    def _calculate_dependency_factor(self, task, context: TaskContext) -> float:
        """Calculate score based on dependencies and blockers"""
        score = 25.0  # Base score
        
        # Penalty for having blockers
        if context.blockers:
            blocker_penalty = len(context.blockers) * 5
            score -= blocker_penalty
        
        # Boost for being ready (no blockers) when others depend on it
        if context.is_blocking_others and not context.blockers:
            score += 15.0
        
        # Small penalty for having many dependencies
        if context.dependencies:
            dependency_penalty = len(context.dependencies) * 2
            score -= dependency_penalty
        
        return max(0.0, min(50.0, score))
    
    def _calculate_complexity_adjustment(self, task, context: TaskContext) -> float:
        """Adjust priority based on task complexity"""
        # More complex tasks get slight priority boost (they need more planning)
        complexity_boost = (context.complexity_score - 3) * 3  # -6 to +6
        
        # Consider effort already invested
        if context.actual_hours_spent > 0:
            investment_boost = min(10.0, context.actual_hours_spent * 2)
        else:
            investment_boost = 0.0
        
        # Consider estimated effort (very large tasks might need breaking down)
        if context.estimated_hours > 8:
            large_task_penalty = -5.0
        else:
            large_task_penalty = 0.0
        
        total_adjustment = 25.0 + complexity_boost + investment_boost + large_task_penalty
        return max(0.0, min(50.0, total_adjustment))
    
    def _calculate_procrastination_penalty(self, task, context: TaskContext, current_time: datetime) -> float:
        """Penalize tasks that have been postponed or neglected"""
        base_score = 25.0
        
        # Penalty for postponements
        postponement_penalty = context.postponement_count * 5
        
        # Penalty for tasks that haven't been touched in a while
        if context.last_updated:
            days_since_update = (current_time - context.last_updated).days
            staleness_penalty = min(15.0, days_since_update * 1.5)
        else:
            staleness_penalty = 0.0
        
        # Penalty for tasks that are way overdue on creation date
        if context.creation_date:
            days_since_creation = (current_time - context.creation_date).days
            if days_since_creation > 30:  # Task older than 30 days
                age_penalty = min(20.0, (days_since_creation - 30) * 0.5)
            else:
                age_penalty = 0.0
        else:
            age_penalty = 0.0
        
        total_penalty = postponement_penalty + staleness_penalty + age_penalty
        final_score = base_score + total_penalty
        
        return min(50.0, final_score)
    
    def _calculate_adaptive_multiplier(self, task, context: TaskContext, current_time: datetime) -> float:
        """Calculate adaptive multiplier based on user patterns and context"""
        multiplier = 1.0
        
        # Time of day factor (can be enhanced with user's productive hours)
        hour = current_time.hour
        if 9 <= hour <= 11 or 14 <= hour <= 16:  # Peak productivity hours
            multiplier *= 1.1
        elif hour < 6 or hour > 22:  # Late night/early morning
            multiplier *= 0.9
        
        # Energy alignment factor
        if hasattr(task, 'energy_level_required'):
            # This could be enhanced with user's current energy level
            # For now, boost high-energy tasks during peak hours
            if context.energy_level_required >= 4 and 9 <= hour <= 11:
                multiplier *= 1.15
            elif context.energy_level_required <= 2 and (hour >= 20 or hour <= 8):
                multiplier *= 1.1
        
        return multiplier
    
    def batch_calculate_priorities(self, tasks: List, contexts: List[TaskContext] = None) -> List[Tuple[float, Dict]]:
        """Efficiently calculate priorities for multiple tasks"""
        if contexts is None:
            contexts = [TaskContext() for _ in tasks]
        
        results = []
        current_time = datetime.utcnow()
        
        for task, context in zip(tasks, contexts):
            score, breakdown = self.calculate_priority_score(task, context, current_time)
            results.append((score, breakdown))
        
        return results
    
    def get_priority_explanation(self, task, context: TaskContext = None) -> str:
        """Get human-readable explanation of priority score"""
        score, breakdown = self.calculate_priority_score(task, context)
        
        explanation = f"Priority Score: {score}/100\n\n"
        
        if score >= 80:
            explanation += "🔥 CRITICAL - Immediate attention required\n"
        elif score >= 60:
            explanation += "🚨 HIGH - Should be prioritized today\n"
        elif score >= 40:
            explanation += "⚠️ MEDIUM - Important but can wait\n"
        elif score >= 20:
            explanation += "📋 LOW - Nice to have\n"
        else:
            explanation += "💤 MINIMAL - Consider if necessary\n"
        
        explanation += "\nBreakdown:\n"
        for factor, value in breakdown.items():
            if factor != 'final_score':
                explanation += f"• {factor.replace('_', ' ').title()}: {value}\n"
        
        return explanation
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Allow dynamic adjustment of priority weights"""
        self.priority_weights.update(new_weights)
        
        # Normalize weights to sum to 1.0
        total = sum(self.priority_weights.values())
        if total != 1.0:
            for key in self.priority_weights:
                self.priority_weights[key] /= total

# Usage Example
if __name__ == "__main__":
    # Example task class (replace with your actual task class)
    class Task:
        def __init__(self, priority=3, deadline=None, completed=False):
            self.priority = priority
            self.deadline = deadline
            self.completed = completed
    
    # Create engine and test
    engine = calculate_priority_score()
    
    # Test task with deadline in 2 hours
    test_task = Task(
        priority=4,
        deadline=datetime.utcnow() + timedelta(hours=2),
        completed=False
    )
    
    # Enhanced context
    context = TaskContext(
        impact_level=ImpactLevel.HIGH,
        task_type=TaskType.URGENT_IMPORTANT,
        is_blocking_others=True,
        complexity_score=4,
        team_size=3,
        postponement_count=1,
        creation_date=datetime.utcnow() - timedelta(days=5)
    )
    
    score, breakdown = engine.calculate_priority_score(test_task, context)
    print(f"Priority Score: {score}")
    print(f"Breakdown: {breakdown}")
    print("\n" + engine.get_priority_explanation(test_task, context))