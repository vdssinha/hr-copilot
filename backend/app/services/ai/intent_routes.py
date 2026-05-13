"""
Utterance corpus for semantic intent routing.

Utterances sourced directly from Requirement.md — "Example User Questions",
"Suggested Evaluation Prompts", and routing examples in Section 4 (AI Router).

Add or remove utterances here to tune routing accuracy — no code changes elsewhere.
UNKNOWN has no route; low-confidence scores fall through to that label automatically.
"""
from app.services.ai.semantic_router import Route

# ── Policy RAG ────────────────────────────────────────────────────────────────
# Source: Requirement.md § Policy RAG Assistant — Example User Questions
#         + Suggested Evaluation Prompts — Policy RAG Prompts
#         + AI Router routing example table

POLICY_QA_ROUTE = Route(
    name="POLICY_QA",
    utterances=[
        # § Policy RAG — Example User Questions
        "How many sick leaves do I get?",
        "What is the work-from-home policy?",
        "Can I take a half-day leave?",
        "What happens if I log in late?",
        "What is the policy for uploading documents?",
        # § Suggested Evaluation Prompts — Policy RAG
        "What is the leave policy?",
        "How many sick leaves can I take?",
        "Can I work from home?",
        "What happens if I am late?",
        # § AI Router — routing example table
        "What is the leave policy?",
        # natural variations on the above
        "What is the maternity leave policy?",
        "What is the paternity leave entitlement?",
        "What is the notice period for resignation?",
        "How does the performance review process work?",
        "What are the overtime rules?",
        "Are there work from home guidelines?",
        "What is the dress code policy?",
        "How many public holidays do we get?",
        "What is the bereavement leave policy?",
        "What is the travel reimbursement policy?",
        "Explain the expense claim procedure.",
        "What is the policy on conflict of interest?",
    ],
)

# ── SQL Agent ─────────────────────────────────────────────────────────────────
# Source: Requirement.md § SQL Agent — Example User Questions
#         + Suggested Evaluation Prompts — SQL Agent Prompts
#         + AI Router routing example table

SQL_QUERY_ROUTE = Route(
    name="SQL_QUERY",
    utterances=[
        # § SQL Agent — Example User Questions
        "Which projects are ongoing?",
        "Who is assigned to the HR Policy Copilot project?",
        "Which employees know Python and FastAPI?",
        "Show my current project assignments.",
        "Find Engineering employees with AI Engineer skills.",
        "Which employees report to my manager?",
        # § Suggested Evaluation Prompts — SQL Agent
        "Which projects are currently ongoing?",
        "Which employees know Python?",
        "Who is assigned to HR Policy Copilot?",
        "Find Engineering employees with FastAPI skills.",
        # § AI Router — routing example table
        "Who is assigned to Project X?",
        "Show employees who know LangChain.",
        # natural variations
        "How many employees are in the engineering department?",
        "List all employees in the marketing team.",
        "What is the headcount by department?",
        "List employees hired this year.",
        "How many tickets were created last month?",
        "Show all active projects.",
        "Which employees have Python skills and are assigned to ongoing projects?",
        "List all open leave requests for my department.",
        "Which employees report to me?",
        "Show me the leave balance for my team.",
        "Which department has the most open tickets?",
        # salary / compensation queries → SQL agent with RBAC
        "What is my salary?",
        "Show me my salary.",
        "What is my current salary?",
        "How much do I earn?",
        "What is my compensation?",
        "Show salary details.",
        "What is the salary of employees in engineering?",
        "Show me my pay.",
        "How much do I get paid?",
        "What is my CTC?",
        # manager salary / other person's salary → SQL agent → ACCESS_DENIED for non-privileged roles
        "Show me my manager's salary.",
        "What is my manager's salary?",
        "How much does my manager earn?",
        "What is my boss's salary?",
        "Show me another employee's salary.",
        "What is Rahul's salary?",
        "How much does Dev Patel earn?",
        # manager / org chart lookups → SQL agent
        "Who is my manager?",
        "Who is my reporting manager?",
        "Who do I report to?",
        "What is my manager's name?",
        "Who manages me?",
        "Tell me who my manager is.",
        "Show me my manager's details.",
        "Who is my direct manager?",
        "What is the name of my manager?",
    ],
)

# ── HR Action Agent ───────────────────────────────────────────────────────────
# Source: Requirement.md § HR Task Automation Agent — Supported Actions
#         + Example User Request
#         + Suggested Evaluation Prompts — HR Action Prompts
#         + AI Router routing example table

HR_ACTION_ROUTE = Route(
    name="HR_ACTION",
    utterances=[
        # § HR Task Automation — Example User Request
        "Apply sick leave from May 6 to May 7 because I have fever.",
        # § Suggested Evaluation Prompts — HR Action
        "Apply casual leave for tomorrow because of personal work.",
        "Create a high-priority IT ticket for VPN not working.",
        "Approve Employee User's pending leave request.",
        "Assign Employee User to HR Policy Copilot as AI Engineer.",
        "Create an announcement that Friday's townhall is moved to 5 PM.",
        # § AI Router — routing example table
        "Apply leave for tomorrow.",
        "Create a ticket for VPN issue.",
        # § Supported Actions — Employee
        "Apply for leave.",
        "Check my leave balance.",
        "Create a support ticket.",
        "Check the status of my ticket.",
        "View my project assignments.",
        # § Supported Actions — Manager
        "Approve the leave request.",
        "Reject this leave request.",
        "Assign this ticket to the IT team.",
        "Show team leave information.",
        "Search for employees with Python skills.",
        "Create an announcement for the whole company.",
        # § Supported Actions — Admin
        "Create a new project called Alpha.",
        "Assign employee to the Phoenix project.",
        # natural variations
        "I want to take annual leave next week.",
        "Submit a leave request for two days.",
        "Raise a ticket for my laptop issue.",
        "Book a day off on Friday.",
        "Put in a holiday request for next month.",
        "Cancel my leave application.",
        "How many sick days do I have left?",
        # today / immediate leave variants
        "Apply for today sick leave.",
        "Apply sick leave for today.",
        "I need sick leave today.",
        "Take a sick day today.",
        "Apply for a sick day today.",
        "Apply casual leave for today.",
        "Apply leave for today.",
        "I am sick today, apply sick leave.",
        "Mark me as on leave today.",
        "Apply for annual leave starting today.",
    ],
)

ALL_ROUTES = [POLICY_QA_ROUTE, SQL_QUERY_ROUTE, HR_ACTION_ROUTE]
