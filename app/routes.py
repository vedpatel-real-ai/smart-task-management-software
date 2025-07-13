from ai.task_priority_engine import calculate_priority_score
priority_engine = calculate_priority_score()
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from .models import User, Task, PlannedTask  # Added PlannedTask
from dateparser.search import search_dates
from . import db, login_manager
from flask_jwt_extended import jwt_required, get_jwt_identity
import re
from datetime import datetime, timedelta, date  # Added date
from sqlalchemy import func, and_, or_
import json
import logging

logger = logging.getLogger(__name__)  # Added logger

main = Blueprint('main', __name__)
planner = Blueprint('planner', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/')
def home():
    """Enhanced landing page with feature highlights"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    features = [
        {'icon': '🧠', 'title': 'AI-Powered Prioritization', 'desc': 'Smart algorithms analyze your tasks to suggest optimal focus areas'},
        {'icon': '⚡', 'title': 'Quick Natural Input', 'desc': 'Add tasks using natural language like "Submit report by Friday 2pm"'},
        {'icon': '📊', 'title': 'Progress Analytics', 'desc': 'Track your productivity with detailed insights and completion trends'},
        {'icon': '🎯', 'title': 'Focus Mode', 'desc': 'Pomodoro timer with your top 3 priority tasks for maximum productivity'}
    ]
    
    return render_template('index.html', features=features)

@main.route('/register', methods=['GET', 'POST'])
def register():
    """Enhanced registration with validation and welcome experience"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        name = request.form.get('name', '').strip()
        
        # Enhanced validation
        errors = []
        
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            errors.append('Password must contain both letters and numbers.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if not name or len(name) < 2:
            errors.append('Please enter your full name.')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered. Please use a different email.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        try:
            new_user = User(
                email=email,
                name=name,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                created_at=datetime.utcnow()
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash('🎉 Welcome to Smart Task Manager! Your account has been created successfully.', 'success')
            return redirect(url_for('main.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Enhanced login with remember me and better UX"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember_me'))
        
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            login_user(user, remember=remember_me)
            
            # Redirect to intended page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            
            flash(f'Welcome back, {user.name}! 👋', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
    
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    """Enhanced logout with confirmation"""
    logout_user()
    flash('You have been logged out successfully. See you soon! 👋', 'info')
    return redirect(url_for('main.home'))

@main.route('/dashboard')
@login_required
def dashboard():
    """Enhanced dashboard with comprehensive overview and insights"""
    today = datetime.utcnow().date()
    
    # Get user tasks with smart scoring
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    # Calculate smart scores
    for task in all_tasks:
        task.smart_score = priority_engine.calculate_priority_score(task)[0]    
    # Dashboard statistics
    stats = {
        'total_tasks': len(all_tasks),
        'completed_today': len([t for t in all_tasks if t.completed and t.updated_at.date() == today]),
        'pending_tasks': len([t for t in all_tasks if not t.completed]),
        'overdue_tasks': len([t for t in all_tasks if not t.completed and t.deadline.date() < today]),
        'due_today': len([t for t in all_tasks if not t.completed and t.deadline.date() == today]),
        'due_this_week': len([t for t in all_tasks if not t.completed and today <= t.deadline.date() <= today + timedelta(days=7)])
    }
    
    # Recent tasks (last 5)
    recent_tasks = sorted([t for t in all_tasks if not t.completed], 
                         key=lambda x: x.created_at, reverse=True)[:5]
    
    # Top priority tasks (top 3 by smart score)
    priority_tasks = sorted([t for t in all_tasks if not t.completed], 
                           key=lambda x: x.smart_score, reverse=True)[:3]
    
    # Weekly completion trend (last 7 days)
    weekly_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        completed = len([t for t in all_tasks if t.completed and t.updated_at.date() == date])
        weekly_data.append({
            'date': date.strftime('%a'),
            'completed': completed
        })
    
    # Productivity insights
    insights = []
    if stats['overdue_tasks'] > 0:
        insights.append({
            'type': 'warning',
            'message': f"You have {stats['overdue_tasks']} overdue task{'s' if stats['overdue_tasks'] > 1 else ''}. Consider reviewing deadlines."
        })
    
    if stats['due_today'] > 0:
        insights.append({
            'type': 'info',
            'message': f"You have {stats['due_today']} task{'s' if stats['due_today'] > 1 else ''} due today. Stay focused!"
        })
    
    if stats['completed_today'] > 0:
        insights.append({
            'type': 'success',
            'message': f"Great job! You've completed {stats['completed_today']} task{'s' if stats['completed_today'] > 1 else ''} today."
        })
    
    return render_template('dashboard.html', 
                         stats=stats,
                         recent_tasks=recent_tasks,
                         priority_tasks=priority_tasks,
                         weekly_data=weekly_data,
                         insights=insights,
                         user=current_user)

@main.route('/tasks')
@login_required
def tasks():
    """Enhanced task list with filtering, sorting, and search"""
    # Get filter parameters
    filter_status = request.args.get('status', 'all')  # all, pending, completed, overdue
    filter_priority = request.args.get('priority', 'all')  # all, 1, 2, 3, 4, 5
    sort_by = request.args.get('sort', 'smart')  # smart, deadline, priority, created
    search_query = request.args.get('search', '').strip()
    
    # Base query
    query = Task.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    today = datetime.utcnow().date()
    
    if filter_status == 'pending':
        query = query.filter_by(completed=False)
    elif filter_status == 'completed':
        query = query.filter_by(completed=True)
    elif filter_status == 'overdue':
        query = query.filter(and_(Task.completed == False, Task.deadline < datetime.utcnow()))
    
    if filter_priority != 'all':
        query = query.filter_by(priority=int(filter_priority))
    
    if search_query:
        query = query.filter(or_(
            Task.title.contains(search_query),
            Task.description.contains(search_query)
        ))
    
    user_tasks = query.all()
    
    # Calculate smart scores and apply sorting
    for task in user_tasks:
        task.smart_score = priority_engine.calculate_priority_score(task)[0]    
    if sort_by == 'smart':
        user_tasks.sort(key=lambda x: x.smart_score, reverse=True)
    elif sort_by == 'deadline':
        user_tasks.sort(key=lambda x: x.deadline)
    elif sort_by == 'priority':
        user_tasks.sort(key=lambda x: x.priority, reverse=True)
    elif sort_by == 'created':
        user_tasks.sort(key=lambda x: x.created_at, reverse=True)
    
    # Categorize tasks for better UX
    categorized_tasks = {
        'overdue': [t for t in user_tasks if not t.completed and t.deadline.date() < today],
        'due_today': [t for t in user_tasks if not t.completed and t.deadline.date() == today],
        'upcoming': [t for t in user_tasks if not t.completed and t.deadline.date() > today],
        'completed': [t for t in user_tasks if t.completed]
    }
    
    return render_template('tasks.html', 
                         tasks=user_tasks,
                         categorized_tasks=categorized_tasks,
                         current_filters={
                             'status': filter_status,
                             'priority': filter_priority,
                             'sort': sort_by,
                             'search': search_query
                         })

@main.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """Enhanced task creation with better validation and templates"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        deadline = request.form.get('deadline')
        priority = request.form.get('priority')
        category = request.form.get('category', '').strip()
        estimated_hours = request.form.get('estimated_hours')
        
        # Validation
        errors = []
        
        if not title:
            errors.append('Task title is required.')
        elif len(title) > 200:
            errors.append('Task title must be less than 200 characters.')
        
        if not deadline:
            errors.append('Deadline is required.')
        else:
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
                if deadline_date < datetime.utcnow():
                    errors.append('Deadline cannot be in the past.')
            except ValueError:
                errors.append('Invalid deadline format.')
        
        if not priority or priority not in ['1', '2', '3', '4', '5']:
            errors.append('Please select a valid priority level.')
        
        if estimated_hours:
            try:
                hours = float(estimated_hours)
                if hours <= 0 or hours > 100:
                    errors.append('Estimated hours must be between 0.1 and 100.')
            except ValueError:
                errors.append('Invalid estimated hours format.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('create_task.html')
        
        try:
            new_task = Task(
                title=title,
                description=description,
                deadline=datetime.strptime(deadline, '%Y-%m-%dT%H:%M'),
                priority=int(priority),
                category=category if category else None,
                estimated_hours=float(estimated_hours) if estimated_hours else None,
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_task)
            db.session.commit()
            
            flash(f'✅ Task "{title}" created successfully!', 'success')
            return redirect(url_for('main.tasks'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating the task. Please try again.', 'error')
    
    # Task templates for quick creation
    templates = [
        {'name': 'Meeting', 'title': 'Team Meeting', 'description': 'Attend scheduled team meeting', 'priority': 3},
        {'name': 'Report', 'title': 'Weekly Report', 'description': 'Prepare and submit weekly progress report', 'priority': 4},
        {'name': 'Review', 'title': 'Code Review', 'description': 'Review pull requests and provide feedback', 'priority': 3},
        {'name': 'Research', 'title': 'Research Task', 'description': 'Conduct research on assigned topic', 'priority': 2}
    ]
    
    return render_template('create_task.html', templates=templates)

@main.route('/tasks/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    """Enhanced task editing with change tracking"""
    task = Task.query.get_or_404(id)
    
    if task.user_id != current_user.id:
        flash('You can only edit your own tasks.', 'error')
        return redirect(url_for('main.tasks'))
    
    if request.method == 'POST':
        # Store original values for change tracking
        original_completed = task.completed
        
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        deadline = request.form.get('deadline')
        priority = request.form.get('priority')
        category = request.form.get('category', '').strip()
        estimated_hours = request.form.get('estimated_hours')
        completed = 'completed' in request.form
        
        # Validation (similar to create_task)
        errors = []
        
        if not title:
            errors.append('Task title is required.')
        
        if not deadline:
            errors.append('Deadline is required.')
        else:
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
            except ValueError:
                errors.append('Invalid deadline format.')
        
        if not priority or priority not in ['1', '2', '3', '4', '5']:
            errors.append('Please select a valid priority level.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('edit_task.html', task=task)
        
        try:
            task.title = title
            task.description = description
            task.deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
            task.priority = int(priority)
            task.category = category if category else None
            task.estimated_hours = float(estimated_hours) if estimated_hours else None
            task.completed = completed
            task.updated_at = datetime.utcnow()
            
            # Track completion
            if not original_completed and completed:
                task.completed_at = datetime.utcnow()
                flash(f'🎉 Congratulations! Task "{title}" marked as completed!', 'success')
            elif original_completed and not completed:
                task.completed_at = None
                flash(f'Task "{title}" marked as pending.', 'info')
            else:
                flash(f'Task "{title}" updated successfully!', 'success')
            
            db.session.commit()
            return redirect(url_for('main.tasks'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating the task. Please try again.', 'error')
    
    return render_template('edit_task.html', task=task)

@main.route('/tasks/<int:id>/delete', methods=['POST'])
@login_required
def delete_task(id):
    """Enhanced task deletion with confirmation"""
    task = Task.query.get_or_404(id)
    
    if task.user_id != current_user.id:
        flash('You can only delete your own tasks.', 'error')
        return redirect(url_for('main.tasks'))
    
    try:
        task_title = task.title
        db.session.delete(task)
        db.session.commit()
        flash(f'Task "{task_title}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the task.', 'error')
    
    return redirect(url_for('main.tasks'))

@main.route('/tasks/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_task(id):
    """Quick toggle task completion status"""
    task = Task.query.get_or_404(id)
    
    if task.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        task.completed = not task.completed
        task.updated_at = datetime.utcnow()
        
        if task.completed:
            task.completed_at = datetime.utcnow()
        else:
            task.completed_at = None
            
        db.session.commit()
        
        return jsonify({
            'success': True,
            'completed': task.completed,
            'message': f'Task {"completed" if task.completed else "reopened"}!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update task'}), 500

@main.route('/focus')
@login_required
def focus():
    """Enhanced focus mode with better task selection and insights"""
    all_tasks = Task.query.filter_by(user_id=current_user.id, completed=False).all()
    
    if not all_tasks:
        flash('No pending tasks found. Create some tasks to use Focus Mode!', 'info')
        return redirect(url_for('main.create_task'))
    
    # Calculate smart scores
    for task in all_tasks:
        task.smart_score = priority_engine.calculate_priority_score(task)[0]    
    # Get top tasks with different criteria
    top_tasks = sorted(all_tasks, key=lambda x: x.smart_score, reverse=True)[:3]
    urgent_tasks = sorted([t for t in all_tasks if t.deadline.date() <= datetime.utcnow().date() + timedelta(days=1)], 
                         key=lambda x: x.deadline)[:3]
    high_priority = sorted([t for t in all_tasks if t.priority >= 4], 
                          key=lambda x: (x.priority, x.smart_score), reverse=True)[:3]
    
    # Focus session recommendations
    recommendations = {
        'smart': {
            'title': 'AI Recommended',
            'description': 'Tasks selected by our smart priority algorithm',
            'tasks': top_tasks,
            'icon': '🧠'
        },
        'urgent': {
            'title': 'Time Sensitive',
            'description': 'Tasks with approaching deadlines',
            'tasks': urgent_tasks,
            'icon': '⏰'
        },
        'priority': {
            'title': 'High Priority',
            'description': 'Tasks marked as high importance',
            'tasks': high_priority,
            'icon': '🔥'
        }
    }
    
    # Focus session stats
    total_estimated_time = sum(t.estimated_hours or 1 for t in top_tasks)
    
    return render_template('focus.html', 
                         recommendations=recommendations,
                         total_estimated_time=total_estimated_time,
                         current_selection='smart')

@main.route('/tasks/quick-add', methods=['GET', 'POST'])
@login_required
def quick_add():
    """Enhanced quick add with better parsing and suggestions"""
    if request.method == 'POST':
        user_input = request.form.get('input', '').strip()
        
        if not user_input:
            flash("Please enter a task description.", 'error')
            return redirect(url_for('main.quick_add'))
        
        try:
            # Enhanced parsing with dateparser
            results = search_dates(
                user_input,
                settings={
                    'PREFER_DATES_FROM': 'future',
                    'TIMEZONE': 'UTC',
                    'RETURN_AS_TIMEZONE_AWARE': False
                }
            )
            
            if not results:
                # If no date found, set default deadline (tomorrow 9 AM)
                tomorrow = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
                title = user_input.capitalize()
                parsed_date = tomorrow
                date_found = False
            else:
                # Extract date and title
                date_text, parsed_date = results[0]
                title_parts = user_input.replace(date_text, '').strip()
                
                # Clean up title
                title = re.sub(r'\b(by|due|before|until)\b', '', title_parts, flags=re.IGNORECASE).strip()
                title = title.capitalize() if title else "Quick Task"
                date_found = True
            
            # Infer priority from keywords
            priority = 3  # default
            priority_keywords = {
                5: ['urgent', 'asap', 'critical', 'emergency', 'immediately'],
                4: ['important', 'high', 'priority', 'must'],
                2: ['low', 'minor', 'small', 'simple'],
                1: ['later', 'someday', 'eventually', 'maybe']
            }
            
            user_input_lower = user_input.lower()
            for p, keywords in priority_keywords.items():
                if any(keyword in user_input_lower for keyword in keywords):
                    priority = p
                    break
            
            # Create task
            new_task = Task(
                title=title,
                description=f"Created via Quick Add: '{user_input}'",
                deadline=parsed_date,
                priority=priority,
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_task)
            db.session.commit()
            
            success_msg = f"✅ Task '{title}' created!"
            if not date_found:
                success_msg += " (Default deadline: tomorrow 9 AM)"
            
            flash(success_msg, 'success')
            return redirect(url_for('main.tasks'))
            
        except Exception as e:
            flash("❌ Sorry, I couldn't parse that. Please try a clearer format like 'Submit report by Friday 2pm'", 'error')
    
    # Provide examples for better UX
    examples = [
        "Submit final report by Friday 5pm",
        "Call dentist tomorrow morning",
        "Review presentation slides by end of week",
        "Buy groceries this weekend",
        "Schedule team meeting next Monday 2pm"
    ]
    
    return render_template('quick_add.html', examples=examples)

@main.route('/progress')
@login_required
def progress():
    """Enhanced progress tracking with detailed analytics"""
    # Date range options
    view_range = request.args.get('range', '7')  # 7, 30, 90 days
    range_days = int(view_range)
    
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=range_days - 1)
    
    # Fetch all user tasks
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    # Filter tasks by date range
    period_tasks = [t for t in all_tasks if t.created_at.date() >= start_date]
    
    # Daily completion data
    daily_data = {}
    for i in range(range_days):
        date = start_date + timedelta(days=i)
        daily_data[date] = {'created': 0, 'completed': 0}
    
    for task in period_tasks:
        task_date = task.created_at.date()
        if task_date in daily_data:
            daily_data[task_date]['created'] += 1
            if task.completed:
                completed_date = task.completed_at.date() if task.completed_at else task.updated_at.date()
                if completed_date in daily_data:
                    daily_data[completed_date]['completed'] += 1
    
    # Prepare chart data
    chart_labels = [date.strftime('%m/%d') for date in sorted(daily_data.keys())]
    created_data = [daily_data[date]['created'] for date in sorted(daily_data.keys())]
    completed_data = [daily_data[date]['completed'] for date in sorted(daily_data.keys())]
    
    # Calculate statistics
    total_created = len(period_tasks)
    total_completed = len([t for t in period_tasks if t.completed])
    completion_rate = round((total_completed / total_created) * 100, 1) if total_created > 0 else 0
    
    # Category breakdown
    category_stats = {}
    for task in period_tasks:
        category = task.category or 'Uncategorized'
        if category not in category_stats:
            category_stats[category] = {'total': 0, 'completed': 0}
        category_stats[category]['total'] += 1
        if task.completed:
            category_stats[category]['completed'] += 1
    
    # Priority breakdown
    priority_stats = {}
    priority_names = {1: 'Very Low', 2: 'Low', 3: 'Medium', 4: 'High', 5: 'Critical'}
    for task in period_tasks:
        priority = priority_names[task.priority]
        if priority not in priority_stats:
            priority_stats[priority] = {'total': 0, 'completed': 0}
        priority_stats[priority]['total'] += 1
        if task.completed:
            priority_stats[priority]['completed'] += 1
    
    # Productivity insights
    insights = []
    
    if completion_rate >= 80:
        insights.append({
            'type': 'success',
            'title': 'Excellent Performance!',
            'message': f'You have a {completion_rate}% completion rate. Keep up the great work!'
        })
    elif completion_rate >= 60:
        insights.append({
            'type': 'info',
            'title': 'Good Progress',
            'message': f'You have a {completion_rate}% completion rate. Consider focusing on fewer tasks for better results.'
        })
    else:
        insights.append({
            'type': 'warning',
            'title': 'Room for Improvement',
            'message': f'Your completion rate is {completion_rate}%. Try using the Focus Mode for better productivity.'
        })
    
    # Best performing day
    if daily_data:
        best_day = max(daily_data.keys(), key=lambda d: daily_data[d]['completed'])
        if daily_data[best_day]['completed'] > 0:
            insights.append({
                'type': 'info',
                'title': 'Most Productive Day',
                'message': f'{best_day.strftime("%A, %B %d")} was your most productive day with {daily_data[best_day]["completed"]} completed tasks.'
            })
    
    return render_template('progress.html',
                         chart_labels=chart_labels,
                         created_data=created_data,
                         completed_data=completed_data,
                         total_created=total_created,
                         total_completed=total_completed,
                         completion_rate=completion_rate,
                         category_stats=category_stats,
                         priority_stats=priority_stats,
                         insights=insights,
                         current_range=view_range)

@main.route('/focus-timer')
@login_required
def focus_timer():
    """Enhanced Pomodoro timer with task integration"""
    # Get current focus tasks
    focus_tasks = Task.query.filter_by(user_id=current_user.id, completed=False).all()
    
    # Calculate smart scores and get top 3
    for task in focus_tasks:
        task.smart_score = priority_engine.calculate_priority_score(task)[0]    
    recommended_tasks = sorted(focus_tasks, key=lambda x: x.smart_score, reverse=True)[:3]
    
    # Timer presets
    timer_presets = [
        {'name': 'Pomodoro', 'work': 25, 'break': 5, 'description': 'Classic productivity technique'},
        {'name': 'Power Hour', 'work': 60, 'break': 15, 'description': 'Extended focus session'},
        {'name': 'Quick Sprint', 'work': 15, 'break': 3, 'description': 'Short burst of productivity'},
        {'name': 'Deep Work', 'work': 90, 'break': 20, 'description': 'Extended deep focus'}
    ]
    
    return render_template('focus_timer.html', 
                         recommended_tasks=recommended_tasks,
                         timer_presets=timer_presets)

@main.route('/api/tasks/search')
@login_required
def api_search_tasks():
    """API endpoint for task search (for autocomplete, etc.)"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not query:
        return jsonify([])
    
    # Search in title and description
    tasks = Task.query.filter(
        and_(
            Task.user_id == current_user.id,
            or_(
                Task.title.contains(query),
                Task.description.contains(query)
            )
        )
    ).limit(limit).all()
    
    results = []
    for task in tasks:
        results.append({
            'id': task.id,
            'title': task.title,
            'description': task.description[:100] + '...' if len(task.description) > 100 else task.description,
            'priority': task.priority,
            'deadline': task.deadline.isoformat(),
            'completed': task.completed,
            'category': task.category
        })
    
    return jsonify(results)

@main.route('/api/tasks/stats')
@login_required
def api_task_stats():
    """API endpoint for real-time task statistics"""
    today = datetime.utcnow().date()
    
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        'total': len(all_tasks),
        'completed': len([t for t in all_tasks if t.completed]),
        'pending': len([t for t in all_tasks if not t.completed]),
        'overdue': len([t for t in all_tasks if not t.completed and t.deadline.date() < today]),
        'due_today': len([t for t in all_tasks if not t.completed and t.deadline.date() == today]),
        'completed_today': len([t for t in all_tasks if t.completed and t.updated_at.date() == today])
    }
    
    return jsonify(stats)

@main.route('/settings')
@login_required
def settings():
    """User settings and preferences"""
    return render_template('settings.html', user=current_user)

@main.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    """Update user settings"""
    try:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        timezone = request.form.get('timezone', 'UTC')
        
        # Validation
        if not name or len(name) < 2:
            flash('Name must be at least 2 characters long.', 'error')
            return redirect(url_for('main.settings'))
        
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('main.settings'))
        
        # Check if email is already taken by another user
        existing_user = User.query.filter(and_(User.email == email, User.id != current_user.id)).first()
        if existing_user:
            flash('Email address is already in use by another account.', 'error')
            return redirect(url_for('main.settings'))
        
        # Update user
        current_user.name = name
        current_user.email = email
        current_user.timezone = timezone
        current_user.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating settings.', 'error')
    
    return redirect(url_for('main.settings'))

@main.route('/settings/password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Validation
    if not check_password_hash(current_user.password, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('main.settings'))
    
    if len(new_password) < 8:
        flash('New password must be at least 8 characters long.', 'error')
        return redirect(url_for('main.settings'))
    
    if not re.search(r'[A-Za-z]', new_password) or not re.search(r'\d', new_password):
        flash('New password must contain both letters and numbers.', 'error')
        return redirect(url_for('main.settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('main.settings'))
    
    try:
        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        current_user.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while changing password.', 'error')
    
    return redirect(url_for('main.settings'))

@main.route('/export')
@login_required
def export_tasks():
    """Export user tasks to CSV/JSON"""
    format_type = request.args.get('format', 'csv').lower()
    
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    if format_type == 'json':
        task_data = []
        for task in tasks:
            task_data.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': task.priority,
                'category': task.category,
                'deadline': task.deadline.isoformat(),
                'completed': task.completed,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat() if task.updated_at else None,
                'estimated_hours': task.estimated_hours
            })
        
        response = jsonify(task_data)
        response.headers['Content-Disposition'] = f'attachment; filename=tasks_{datetime.utcnow().strftime("%Y%m%d")}.json'
        return response
    
    else:  # CSV format
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Title', 'Description', 'Priority', 'Category', 
            'Deadline', 'Completed', 'Completed At', 'Created At', 
            'Updated At', 'Estimated Hours'
        ])
        
        # Write task data
        for task in tasks:
            writer.writerow([
                task.id,
                task.title,
                task.description,
                task.priority,
                task.category or '',
                task.deadline.strftime('%Y-%m-%d %H:%M'),
                'Yes' if task.completed else 'No',
                task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else '',
                task.created_at.strftime('%Y-%m-%d %H:%M'),
                task.updated_at.strftime('%Y-%m-%d %H:%M') if task.updated_at else '',
                task.estimated_hours or ''
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=tasks_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        
        return response

@main.route('/analytics')
@login_required
def analytics():
    """Advanced analytics dashboard"""
    # Date range
    days = int(request.args.get('days', 30))
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    
    # Get all user tasks
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    period_tasks = [t for t in all_tasks if t.created_at.date() >= start_date]
    
    # Productivity metrics
    total_tasks = len(period_tasks)
    completed_tasks = len([t for t in period_tasks if t.completed])
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Average completion time
    completed_with_time = [t for t in period_tasks if t.completed and t.completed_at]
    avg_completion_time = 0
    if completed_with_time:
        total_time = sum((t.completed_at - t.created_at).total_seconds() for t in completed_with_time)
        avg_completion_time = total_time / len(completed_with_time) / 3600  # in hours
    
    # Task priority distribution
    priority_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for task in period_tasks:
        priority_dist[task.priority] += 1
    
    # Completion by day of week
    weekday_completion = {i: {'total': 0, 'completed': 0} for i in range(7)}
    for task in period_tasks:
        weekday = task.created_at.weekday()
        weekday_completion[weekday]['total'] += 1
        if task.completed:
            weekday_completion[weekday]['completed'] += 1
    
    # Monthly trend
    monthly_data = {}
    for task in all_tasks:
        month_key = task.created_at.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'created': 0, 'completed': 0}
        monthly_data[month_key]['created'] += 1
        if task.completed:
            monthly_data[month_key]['completed'] += 1
    
    # Performance insights
    insights = []
    
    # Best performing weekday
    best_weekday = max(weekday_completion.keys(), 
                      key=lambda d: weekday_completion[d]['completed'])
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    if weekday_completion[best_weekday]['completed'] > 0:
        insights.append({
            'title': 'Most Productive Day',
            'value': weekday_names[best_weekday],
            'description': f"You complete most tasks on {weekday_names[best_weekday]}s"
        })
    
    # Average tasks per day
    avg_tasks_per_day = total_tasks / days if days > 0 else 0
    insights.append({
        'title': 'Daily Task Average',
        'value': f"{avg_tasks_per_day:.1f}",
        'description': f"Average tasks created per day over the last {days} days"
    })
    
    # Completion streak
    current_streak = 0
    streak_date = end_date
    while streak_date >= start_date:
        day_tasks = [t for t in all_tasks if t.created_at.date() == streak_date and t.completed]
        if day_tasks:
            current_streak += 1
            streak_date -= timedelta(days=1)
        else:
            break
    
    if current_streak > 0:
        insights.append({
            'title': 'Current Streak',
            'value': f"{current_streak} days",
            'description': "Days with at least one completed task"
        })
    
    return render_template('analytics.html',
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         completion_rate=round(completion_rate, 1),
                         avg_completion_time=round(avg_completion_time, 1),
                         priority_dist=priority_dist,
                         weekday_completion=weekday_completion,
                         monthly_data=monthly_data,
                         insights=insights,
                         current_period=days)

@main.route('/help')
def help_page():
    """Help and documentation page"""
    help_sections = [
        {
            'title': 'Getting Started',
            'items': [
                {'q': 'How do I create my first task?', 'a': 'Go to Tasks > Create Task or use the Quick Add feature for natural language input.'},
                {'q': 'What is the Smart Priority System?', 'a': 'Our AI analyzes your tasks based on deadline urgency, priority level, and completion patterns to suggest the most important tasks.'},
                {'q': 'How does Quick Add work?', 'a': 'Simply type tasks in natural language like "Submit report by Friday 2pm" and our system will parse the details automatically.'}
            ]
        },
        {
            'title': 'Focus Mode & Timer',
            'items': [
                {'q': 'What is Focus Mode?', 'a': 'Focus Mode shows your top 3 most important tasks based on AI analysis, helping you concentrate on what matters most.'},
                {'q': 'How do I use the Pomodoro Timer?', 'a': 'Select a task, choose your preferred time setting (25min work/5min break is recommended), and start focusing!'},
                {'q': 'Can I customize timer settings?', 'a': 'Yes! We offer multiple presets: Pomodoro (25/5), Power Hour (60/15), Quick Sprint (15/3), and Deep Work (90/20).'}
            ]
        },
        {
            'title': 'Analytics & Progress',
            'items': [
                {'q': 'How is my completion rate calculated?', 'a': 'Completion rate is the percentage of tasks you\'ve completed within a selected time period.'},
                {'q': 'What insights can I get?', 'a': 'View your most productive days, completion trends, task distribution by priority, and performance streaks.'},
                {'q': 'Can I export my data?', 'a': 'Yes! Go to Settings to export your tasks in CSV or JSON format for backup or analysis.'}
            ]
        }
    ]
    
    return render_template('help.html', help_sections=help_sections)

def validate_task_data(data, required_fields=None):
    """Validate incoming task data"""
    if required_fields is None:
        required_fields = ['title']
    
    errors = []
    
    # Check required fields
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"{field} is required")
    
    # Validate title length
    if 'title' in data and len(data['title']) > 255:
        errors.append("Title must be 255 characters or less")
    
    # Validate priority
    if 'priority' in data and data['priority'] not in ['Low', 'Medium', 'High']:
        errors.append("Priority must be Low, Medium, or High")
    
    # Validate date format
    if 'date' in data:
        try:
            datetime.strptime(data['date'], "%Y-%m-%d")
        except ValueError:
            errors.append("Date must be in YYYY-MM-DD format")
    
    # Validate time format
    if 'time' in data and data['time']:
        try:
            datetime.strptime(data['time'], "%H:%M")
        except ValueError:
            errors.append("Time must be in HH:MM format")
    
    return errors

@planner.route("/api/daily-planner", methods=["GET"])
@login_required
def get_daily_tasks():
    """Get planner tasks with advanced filtering options"""
    try:
        user_id = current_user.id
        
        # Get query parameters
        selected_date = request.args.get("date", date.today().isoformat())
        priority_filter = request.args.get("priority")
        completed_filter = request.args.get("completed")
        search_query = request.args.get("search", "").strip()
        
        # Build base query
        query = PlannedTask.query.filter_by(user_id=user_id, date=selected_date)
        
        # Apply filters
        if priority_filter and priority_filter in ['Low', 'Medium', 'High']:
            query = query.filter(PlannedTask.priority == priority_filter)
        
        if completed_filter is not None:
            is_completed = completed_filter.lower() == 'true'
            query = query.filter(PlannedTask.completed == is_completed)
        
        if search_query:
            query = query.filter(PlannedTask.title.ilike(f"%{search_query}%"))
        
        # Order by priority and time
        priority_order = {
            'High': 1,
            'Medium': 2,
            'Low': 3
        }
        
        tasks = query.all()
        
        # Sort tasks by priority and time
        def sort_key(task):
            priority_num = priority_order.get(task.priority, 4)
            time_num = task.time.hour * 60 + task.time.minute if task.time else 9999
            return (task.completed, priority_num, time_num)
        
        tasks.sort(key=sort_key)
        
        # Get task statistics
        all_tasks = PlannedTask.query.filter_by(user_id=user_id, date=selected_date).all()
        stats = {
            'total': len(all_tasks),
            'completed': sum(1 for task in all_tasks if task.completed),
            'pending': sum(1 for task in all_tasks if not task.completed),
            'high_priority': sum(1 for task in all_tasks if task.priority == 'High'),
            'completion_rate': round((sum(1 for task in all_tasks if task.completed) / len(all_tasks)) * 100, 1) if all_tasks else 0
        }
        
        return jsonify({
            'tasks': [task.to_dict() for task in tasks],
            'stats': stats,
            'date': selected_date
        })
        
    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        return jsonify({'error': 'Failed to fetch tasks'}), 500

@planner.route("/api/daily-planner", methods=["POST"])
@login_required
def add_planner_task():
    """Add a new task with comprehensive validation"""
    try:
        user_id = current_user.id
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        errors = validate_task_data(data, ['title'])
        if errors:
            return jsonify({'errors': errors}), 400
        
        # Check for duplicate tasks on the same date
        existing_task = PlannedTask.query.filter_by(
            user_id=user_id,
            title=data['title'],
            date=datetime.strptime(data.get('date', date.today().isoformat()), "%Y-%m-%d").date()
        ).first()
        
        if existing_task:
            return jsonify({'error': 'A task with this title already exists for this date'}), 409
        
        # Create new task
        task = PlannedTask(
            user_id=user_id,
            title=data['title'].strip(),
            date=datetime.strptime(data.get('date', date.today().isoformat()), "%Y-%m-%d").date(),
            time=datetime.strptime(data['time'], "%H:%M").time() if data.get('time') else None,
            is_recurring=data.get('is_recurring', False),
            priority=data.get('priority', 'Medium')
        )
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"Task created successfully: {task.title} for user {user_id}")
        
        return jsonify({
            'message': 'Task created successfully',
            'task': task.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid date or time format'}), 400
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create task'}), 500

@planner.route("/api/daily-planner/<int:task_id>", methods=["PATCH"])
@login_required
def update_planner_task(task_id):
    """Update task with comprehensive field support"""
    try:
        user_id = current_user.id
        task = PlannedTask.query.filter_by(id=task_id, user_id=user_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Only validate fields that are present
        errors = []
        if 'title' in data:
            if not data['title'] or len(data['title']) > 255:
                errors.append("Title must be present and 255 characters or less")
        if 'priority' in data:
            if data['priority'] not in ['Low', 'Medium', 'High']:
                errors.append("Priority must be Low, Medium, or High")
        if 'date' in data:
            try:
                datetime.strptime(data['date'], "%Y-%m-%d")
            except ValueError:
                errors.append("Date must be in YYYY-MM-DD format")
        if 'time' in data and data['time']:
            try:
                datetime.strptime(data['time'], "%H:%M")
            except ValueError:
                errors.append("Time must be in HH:MM format")
        if errors:
            return jsonify({'errors': errors}), 400
        
        # Track changes for logging
        changes = []
        
        # Update fields
        if 'title' in data:
            old_title = task.title
            task.title = data['title'].strip()
            changes.append(f"title: '{old_title}' -> '{task.title}'")
        
        if 'completed' in data:
            old_status = task.completed
            task.completed = bool(data['completed'])
            changes.append(f"completed: {old_status} -> {task.completed}")
        
        if 'priority' in data:
            old_priority = task.priority
            task.priority = data['priority']
            changes.append(f"priority: {old_priority} -> {task.priority}")
        
        if 'time' in data:
            old_time = task.time
            task.time = datetime.strptime(data['time'], "%H:%M").time() if data['time'] else None
            changes.append(f"time: {old_time} -> {task.time}")
        
        if 'date' in data:
            old_date = task.date
            task.date = datetime.strptime(data['date'], "%Y-%m-%d").date()
            changes.append(f"date: {old_date} -> {task.date}")
        
        if 'is_recurring' in data:
            old_recurring = task.is_recurring
            task.is_recurring = bool(data['is_recurring'])
            changes.append(f"is_recurring: {old_recurring} -> {task.is_recurring}")

            db.session.commit()
        
        logger.info(f"Task {task_id} updated by user {user_id}: {', '.join(changes)}")
        
        return jsonify({
            'message': 'Task updated successfully',
            'task': task.to_dict(),
            'changes': changes
        })
        
    except ValueError as e:
        return jsonify({'error': 'Invalid date or time format'}), 400
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update task'}), 500

@planner.route("/api/daily-planner/<int:task_id>", methods=["DELETE"])
@login_required
def delete_planner_task(task_id):
    """Delete a specific task"""
    try:
        user_id = current_user.id
        task = PlannedTask.query.filter_by(id=task_id, user_id=user_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        task_title = task.title
        db.session.delete(task)
        db.session.commit()
        
        logger.info(f"Task deleted: '{task_title}' by user {user_id}")
        
        return jsonify({'message': 'Task deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete task'}), 500

@planner.route("/api/daily-planner/bulk", methods=["POST"])
@login_required
def bulk_task_operations():
    """Perform bulk operations on tasks"""
    try:
        user_id = current_user.id
        data = request.json
        
        if not data or 'action' not in data or 'task_ids' not in data:
            return jsonify({'error': 'Action and task_ids are required'}), 400
        
        action = data['action']
        task_ids = data['task_ids']
        
        if not isinstance(task_ids, list) or not task_ids:
            return jsonify({'error': 'task_ids must be a non-empty array'}), 400
        
        # Get tasks belonging to the user
        tasks = PlannedTask.query.filter(
            and_(PlannedTask.id.in_(task_ids), PlannedTask.user_id == user_id)
        ).all()
        
        if not tasks:
            return jsonify({'error': 'No valid tasks found'}), 404
        
        updated_tasks = []
        
        if action == 'mark_completed':
            for task in tasks:
                task.completed = True
                updated_tasks.append(task.to_dict())
        
        elif action == 'mark_pending':
            for task in tasks:
                task.completed = False
                updated_tasks.append(task.to_dict())
        
        elif action == 'delete':
            for task in tasks:
                db.session.delete(task)
            db.session.commit()
            return jsonify({
                'message': f'Successfully deleted {len(tasks)} tasks',
                'deleted_count': len(tasks)
            }), 200
        
        elif action == 'update_priority':
            new_priority = data.get('priority')
            if new_priority not in ['Low', 'Medium', 'High']:
                return jsonify({'error': 'Invalid priority value'}), 400
            
            for task in tasks:
                task.priority = new_priority
                updated_tasks.append(task.to_dict())
        
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        
        logger.info(f"Bulk operation '{action}' performed on {len(tasks)} tasks by user {user_id}")
        
        return jsonify({
            'message': f'Successfully {action} {len(tasks)} tasks',
            'updated_tasks': updated_tasks,
            'affected_count': len(tasks)
        })
        
    except Exception as e:
        logger.error(f"Error in bulk operation: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to perform bulk operation'}), 500

@planner.route("/api/daily-planner/week", methods=["GET"])
@login_required
def get_weekly_tasks():
    """Get tasks for the entire week"""
    try:
        user_id = current_user.id
        
        # Get start of week (Monday)
        start_date_str = request.args.get("start_date", date.today().isoformat())
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        
        # Calculate week range
        start_of_week = start_date - timedelta(days=start_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # Get all tasks for the week
        tasks = PlannedTask.query.filter(
            and_(
                PlannedTask.user_id == user_id,
                PlannedTask.date >= start_of_week,
                PlannedTask.date <= end_of_week
            )
        ).all()
        
        # Group tasks by date
        weekly_tasks = {}
        for single_date in (start_of_week + timedelta(n) for n in range(7)):
            date_str = single_date.isoformat()
            weekly_tasks[date_str] = {
                'date': date_str,
                'day_name': single_date.strftime('%A'),
                'tasks': []
            }
        
        for task in tasks:
            date_str = task.date.isoformat()
            if date_str in weekly_tasks:
                weekly_tasks[date_str]['tasks'].append(task.to_dict())
        
        # Calculate weekly statistics
        total_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.completed)
        
        weekly_stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0,
            'start_date': start_of_week.isoformat(),
            'end_date': end_of_week.isoformat()
        }
        
        return jsonify({
            'weekly_tasks': weekly_tasks,
            'stats': weekly_stats
        })
        
    except Exception as e:
        logger.error(f"Error fetching weekly tasks: {str(e)}")
        return jsonify({'error': 'Failed to fetch weekly tasks'}), 500

@planner.route("/api/daily-planner/analytics", methods=["GET"])
@login_required
def get_task_analytics():
    """Get task analytics and insights"""
    try:
        user_id = current_user.id
        
        # Get date range (default to last 30 days)
        days = int(request.args.get("days", 30))
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get tasks in date range
        tasks = PlannedTask.query.filter(
            and_(
                PlannedTask.user_id == user_id,
                PlannedTask.date >= start_date,
                PlannedTask.date <= end_date
            )
        ).all()
        
        # Calculate analytics
        total_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.completed)
        
        # Priority distribution
        priority_counts = {'High': 0, 'Medium': 0, 'Low': 0}
        for task in tasks:
            priority_counts[task.priority] += 1
        
        # Daily completion rates
        daily_stats = {}
        for task in tasks:
            date_str = task.date.isoformat()
            if date_str not in daily_stats:
                daily_stats[date_str] = {'total': 0, 'completed': 0}
            daily_stats[date_str]['total'] += 1
            if task.completed:
                daily_stats[date_str]['completed'] += 1
        
        # Calculate streaks
        current_streak = 0
        max_streak = 0
        temp_streak = 0
        
        for single_date in (start_date + timedelta(n) for n in range(days + 1)):
            date_str = single_date.isoformat()
            if date_str in daily_stats:
                day_stats = daily_stats[date_str]
                if day_stats['total'] > 0 and day_stats['completed'] == day_stats['total']:
                    temp_streak += 1
                    max_streak = max(max_streak, temp_streak)
                else:
                    temp_streak = 0
            else:
                temp_streak = 0
        
        current_streak = temp_streak
        
        analytics = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0,
            'priority_distribution': priority_counts,
            'current_streak': current_streak,
            'max_streak': max_streak,
            'daily_stats': daily_stats,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            }
        }
        
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500

# Error handlers
@main.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@main.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@main.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403