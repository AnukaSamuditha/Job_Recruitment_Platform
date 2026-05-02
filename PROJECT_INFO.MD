# 🧑‍💼 AI Recruitment Screening System (Multi-Agent System)

## 📌 Project Overview

The **AI Recruitment Screening System** is a locally hosted Multi-Agent System (MAS) designed to automate and optimize the candidate screening process.

Recruiters often spend significant time manually reviewing CVs, evaluating skills, ranking candidates, and preparing interview questions. This system simulates an **AI hiring team**, where multiple intelligent agents collaborate, communicate, and make decisions to streamline recruitment.

The system is built using a **multi-agent architecture**, where each agent has a specialized role and interacts with others to produce a final, well-informed outcome.

---

## 🎯 Problem Statement

Filtering and evaluating job applicants is:

* Time-consuming
* Prone to inconsistency
* Difficult to scale with large volumes of CVs

This system addresses these challenges by:

* Automating CV parsing
* Matching candidates against job requirements
* Ranking applicants objectively
* Generating personalized interview questions

---

## 🧠 System Architecture

The system follows a **multi-agent orchestration model**, where multiple agents collaborate through shared state and structured communication.

### 🔹 Core Components

* Multi-Agent Orchestrator (e.g., LangGraph / CrewAI)
* Local LLM (via Ollama)
* Custom Python Tools
* Shared Global State
* Logging & Observability Layer

---

## 🤖 Agents and Responsibilities

### 1. CV Parser Agent

**Role:** Extract structured information from candidate CVs

**Responsibilities:**

* Read and process CV documents
* Extract candidate details such as:

  * Name
  * Skills
  * Experience
  * Education
* Convert unstructured text into structured data

---

### 2. Skill Matcher Agent

**Role:** Evaluate how well a candidate matches the job description

**Responsibilities:**

* Compare extracted skills with job requirements
* Identify:

  * Matching skills
  * Missing skills
* Generate a match score based on relevance

---

### 3. Ranking Agent

**Role:** Rank candidates based on multiple evaluation criteria

**Responsibilities:**

* Aggregate candidate scores
* Apply weighted evaluation (e.g., skills, experience, education)
* Rank candidates relative to others
* Provide justification for ranking decisions

---

### 4. Interview Question Generator Agent

**Role:** Generate personalized interview questions

**Responsibilities:**

* Create technical questions based on candidate skills
* Generate questions targeting missing or weak areas
* Produce behavioral questions
* Adapt questions based on candidate ranking

---

## 🔄 Agent Communication & Workflow

Unlike a simple pipeline, this system enables **active communication between agents**, including feedback loops and decision refinement.

### 🧩 Workflow Overview

1. The **CV Parser Agent** extracts structured candidate data
2. The **Skill Matcher Agent** evaluates the candidate against the job description
3. The **Ranking Agent** ranks candidates based on computed scores
4. The **Interview Agent** generates customized interview questions

### 🔁 Communication Patterns

* Agents **share structured data via global state**
* Agents **respond to outputs from other agents**
* Feedback loops allow:

  * Re-evaluation of candidate scores
  * Adjustment of ranking criteria
* Agents may **challenge or refine decisions** made by others

---

## 🧰 Tools and Integration

The system includes custom-built tools that enable agents to interact with real-world data:

### 🔹 Key Tools

* **PDF Reader Tool** – Extracts text from CV documents
* **Skill Extraction Tool** – Identifies relevant skills from text
* **Matching Tool** – Computes similarity between CV and job description
* **Ranking Tool** – Sorts and ranks candidates

These tools ensure agents rely on **external data and logic**, rather than only internal LLM knowledge.

---

## 🗂️ State Management

A **global shared state** is used to maintain and pass information between agents.

### 🔹 State Includes:

* Job description
* Candidate profiles
* Extracted CV data
* Match scores
* Rankings
* Generated interview questions

### 🔹 Key Features:

* Ensures **context is preserved across agents**
* Allows agents to **read and update shared data**
* Prevents loss of information during transitions

---

## 📊 Observability & Logging (AgentOps)

The system includes a logging mechanism to track all agent activities.

### 🔹 Logged Information:

* Agent inputs and outputs
* Tool usage and results
* Decision-making steps
* Errors and edge cases

### 🔹 Purpose:

* Improve transparency
* Enable debugging
* Support evaluation and testing

---

## 🧪 Testing & Evaluation

The system includes automated evaluation to ensure reliability and correctness.

### 🔹 Evaluation Criteria:

* Accuracy of skill extraction
* Correctness of matching scores
* Fairness of candidate ranking
* Quality of generated interview questions

### 🔹 Test Scenarios:

* Valid CV inputs
* Missing or incomplete CV data
* Candidates with no matching skills
* Multiple candidate comparisons

---

## 🎥 Demonstration Workflow

The system demonstration includes:

1. Uploading one or more CVs
2. Parsing and extracting candidate data
3. Matching candidates with a job description
4. Displaying ranked candidates
5. Generating interview questions

The demo highlights the **end-to-end workflow and agent collaboration**.

---

## 🚀 Key Features

* Multi-agent collaboration and communication
* Automated candidate evaluation pipeline
* Real-time decision-making and ranking
* Personalized interview preparation
* Fully local execution (no paid APIs required)

---

## 🔥 Advanced Enhancements (Optional)

To further improve the system:

* Introduce **conflict resolution between agents**
* Implement **dynamic scoring weights** based on job roles
* Add **multi-candidate comparison dashboards**
* Provide **explainable AI outputs** (justifications for rankings)

---

## 🏆 Conclusion

This project demonstrates a complete **Agentic AI system** where multiple specialized agents:

* Perceive and process data
* Communicate and collaborate
* Use tools to interact with the environment
* Produce meaningful, real-world outcomes

The system aligns with all key requirements of a Multi-Agent System, including orchestration, tool usage, state management, and observability, making it a strong candidate for high academic evaluation.

---
