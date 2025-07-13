from app import db
from flask_login import UserMixin
from datetime import datetime, date, time
from sqlalchemy import Index

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    timezone = db.Column(db.String(50), default='UTC')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    tasks = db.relationship('Task', backref='owner', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=False)
    priority = db.Column(db.Integer, default=3)  # 1-5
    category = db.Column(db.String(100))
    estimated_hours = db.Column(db.Float)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    smart_score = db.Column(db.Float, default=0)  # For AI scoring, not required but can be useful

class PlannedTask(db.Model):
    __tablename__ = 'planned_tasks'
    
    # Primary fields
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)  # Optional detailed description
    
    # Date and time fields
    date = db.Column(db.Date, nullable=False, default=date.today)
    time = db.Column(db.Time, nullable=True)
    estimated_duration = db.Column(db.Integer, nullable=True)  # Duration in minutes
    
    # Task properties
    priority = db.Column(db.String(10), default='Medium')  # Low, Medium, High
    category = db.Column(db.String(50), nullable=True)  # Work, Personal, Health, etc.
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    
    # Status fields
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Recurring task fields
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_type = db.Column(db.String(20), nullable=True)  # daily, weekly, monthly
    recurring_interval = db.Column(db.Integer, default=1)  # Every N days/weeks/months
    recurring_days = db.Column(db.String(20), nullable=True)  # For weekly: "1,2,3,4,5" (Mon-Fri)
    recurring_end_date = db.Column(db.Date, nullable=True)
    parent_task_id = db.Column(db.Integer, db.ForeignKey('planned_tasks.id'), nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subtasks = db.relationship('PlannedTask', 
                              backref=db.backref('parent_task', remote_side=[id]), 
                              lazy='dynamic')
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'date'),
        Index('idx_user_completed', 'user_id', 'completed'),
        Index('idx_user_priority', 'user_id', 'priority'),
        Index('idx_recurring', 'is_recurring', 'recurring_type'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set completed_at when task is marked as completed
        if self.completed and not self.completed_at:
            self.completed_at = datetime.utcnow()
    
    def mark_completed(self):
        """Mark task as completed and set completion timestamp"""
        self.completed = True
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_pending(self):
        """Mark task as pending and clear completion timestamp"""
        self.completed = False
        self.completed_at = None
        self.updated_at = datetime.utcnow()
    
    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def set_tags_list(self, tags_list):
        """Set tags from a list"""
        if tags_list:
            self.tags = ','.join([tag.strip() for tag in tags_list if tag.strip()])
        else:
            self.tags = None
    
    def get_priority_weight(self):
        """Get numeric weight for priority sorting"""
        priority_weights = {'High': 1, 'Medium': 2, 'Low': 3}
        return priority_weights.get(self.priority, 4)
    
    def is_overdue(self):
        """Check if task is overdue"""
        if self.completed:
            return False
        
        task_datetime = datetime.combine(self.date, self.time if self.time else datetime.min.time())
        return task_datetime < datetime.now()
    
    def get_duration_display(self):
        """Get human-readable duration"""
        if not self.estimated_duration:
            return None
        
        hours = self.estimated_duration // 60
        minutes = self.estimated_duration % 60
        
        if hours > 0:
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
        else:
            return f"{minutes}m"
    
    def to_dict(self, include_subtasks=False):
        """Convert task to dictionary representation"""
        result = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'date': self.date.isoformat(),
            'time': self.time.strftime('%H:%M') if self.time else None,
            'estimated_duration': self.estimated_duration,
            'duration_display': self.get_duration_display(),
            'priority': self.priority,
            'priority_weight': self.get_priority_weight(),
            'category': self.category,
            'tags': self.get_tags_list(),
            'completed': self.completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'is_recurring': self.is_recurring,
            'recurring_type': self.recurring_type,
            'recurring_interval': self.recurring_interval,
            'recurring_days': self.recurring_days,
            'recurring_end_date': self.recurring_end_date.isoformat() if self.recurring_end_date else None,
            'parent_task_id': self.parent_task_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_overdue': self.is_overdue(),
            'has_subtasks': self.subtasks.count() > 0
        }
        
        if include_subtasks:
            result['subtasks'] = [subtask.to_dict() for subtask in self.subtasks]
        
        return result
    
    def to_simple_dict(self):
        """Convert task to simple dictionary for API responses"""
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date.isoformat(),
            'time': self.time.strftime('%H:%M') if self.time else None,
            'priority': self.priority,
            'completed': self.completed,
            'category': self.category,
            'is_overdue': self.is_overdue()
        }
    
    @classmethod
    def get_tasks_by_date_range(cls, user_id, start_date, end_date, include_completed=True):
        """Get tasks within a date range"""
        query = cls.query.filter(
            cls.user_id == user_id,
            cls.date >= start_date,
            cls.date <= end_date
        )
        
        if not include_completed:
            query = query.filter(cls.completed == False)
        
        return query.all()
    
    @classmethod
    def get_overdue_tasks(cls, user_id):
        """Get all overdue tasks for a user"""
        today = date.today()
        return cls.query.filter(
            cls.user_id == user_id,
            cls.completed == False,
            cls.date < today
        ).all()
    
    @classmethod
    def get_upcoming_tasks(cls, user_id, days=7):
        """Get upcoming tasks within specified days"""
        start_date = date.today()
        end_date = start_date + timedelta(days=days)
        
        return cls.query.filter(
            cls.user_id == user_id,
            cls.completed == False,
            cls.date >= start_date,
            cls.date <= end_date
        ).order_by(cls.date.asc(), cls.time.asc()).all()
    
    @classmethod
    def get_tasks_by_category(cls, user_id, category, include_completed=True):
        """Get tasks by category"""
        query = cls.query.filter(
            cls.user_id == user_id,
            cls.category == category
        )
        
        if not include_completed:
            query = query.filter(cls.completed == False)
        
        return query.all()
    
    @classmethod
    def search_tasks(cls, user_id, search_term, include_completed=True):
        """Search tasks by title or description"""
        query = cls.query.filter(
            cls.user_id == user_id,
            db.or_(
                cls.title.ilike(f'%{search_term}%'),
                cls.description.ilike(f'%{search_term}%')
            )
        )
        
        if not include_completed:
            query = query.filter(cls.completed == False)
        
        return query.all()
    
    def __repr__(self):
        return f'<PlannedTask {self.id}: {self.title} ({self.date})>'