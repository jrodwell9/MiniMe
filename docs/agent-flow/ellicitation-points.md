# Ellicitation Points

A document to define how human ellicitation should be collected, stored and processed to enable to agentic system to not only learn my preferences but also to evolve and improve as time goes on.

## Problems to Address

### The Sycophancy Problem

By always tailoring the agents trajectories to the way I would have gone about a problem could result in overall sub-optimal 
outcomes given I'm certainly no expert in areas such as web development.

*How can the system balance exploitation of the available ellicitation data with exploration of different strategies?*

- Can we utilise island genetic algorithms with stochasticity?
- Present more than one solution to a user and let them pick by suggesting multiple PRs

### Asynchronous Ellicitation

For a truly asynchronous design the agent will need to be able to request human involvement at all hours of the day, which will in turn require alerting and waiting for a response (perhaps for hours or even days). We ideally don't want the system hanging for that amount of time and burning resources.

*How can we efficiently pause a system, store it's state and then restart from this point over the course of hours/days?*

- Intelligent offloading of conversational history to persistent disk
- Reinstate history on system restart
- Need to store compact summary of history to prevent context bloat

### Storage Bloat

Ideally we want to store all ellicitation as this will allow the system to adapt to my styles in the best way. However, this will mean storing a huge amount of unstructured data which will over time become less and less relevant as both the system and I evolve.

*How can we efficiently store human feedback efficiently and consolidate this into wider topics as time goes on?*

- Storing summaries of trajectories to reduce size
- Scheduled consolidation to maintain knowledge base
- Automatic retirement of knowledge records

## Points of Human Contact (PHC)

Points of human contact are any point in the system where an agent requires human input to be able to continue on with it's task. This could be caused by an agent:

- Getting stuck (from an error or system issue)
- Updating a permanent protected resource
- Collecting feedback
- High stakes decisions

### User Interfaces for PHC

GitHub and other systems have robust and mature eco-systems for showing human users what has changed in codebases along with rich toolkits like the git CLI for managing and isolating changes. As such, we should utilise these as much as possible and leverage ready made tools where possible.

These systems include:

- GitHub - good for asynchronous feedback through comments/commits etc
- Continue chat window - better for synchornous feedback
- CLI messages - works for synchronous feedback and may offer a simpler alternative to chat window integration

### Software Development Lifecycle (SDLC) PHCs

The different kinds of feedback required for the SDLC agents are:

- Test Strategy
- Code Execution Error
- Overall Solution

#### Test Strategy

Feedback to determine whether a test strategy covers all the relevant points of a feature request and to check for any missed edge cases.

This ellicitation can be gleaned from either GitHub or chat interface depending on the availability of a human

#### Code Execution Error

This is a major blocker for the agwent but a valuable point at which to collate feedback and learn from past mistakes.

An event such as this will require multiple pieces of data to be passed to the human evaluator for them to give an informed response, this could include:

- Traceback
- Summary of Error
- Potential Solutions
- Steps to Recreate

This is best presented back to the user through a chat like interface due to it's freeform nature and the probable need of a user to explore the codebase.

#### Overall Solution

Critiquing the overall solution is more of a high level feedback mechanism and may have result in feedback for more than 1 component of the agentic system.

Given the overall solution is best presented back to a human through the medium of a pull request, this element would best sit on GitHub and use GitHub PR comments/suggestions to collect feedback.
