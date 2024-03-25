**KEY FEATURES**

- **Security and Privacy First**: This recommendation workflow only requires an internet connection for installation and upgrades. All recommendation processes operate on your local Terminus Edge, ensuring no data is sent to third-party servers. Your personal behavioral data is encrypted and stored locally for added security.

- **Personalized Content Curation**: This recommendation algorithm learns from your interactions, such as reads, likes, and bookmarks, to create a dynamic user profile. It will automatically adjust recommendations based on changes in your behavior and global news trends.

- **Easy Monitoring**: This recommendation workflow utilize a simple and clear workflow to coordinate the entire content filtering and sorting process. Detailed logs are collected, providing a clear and concise view of all ongoing processes. This improves workflow transparency, assisting you in understanding what kind of content is being filtered out, and preventing information cocoons.

- ** Lightweight Design**: This recommendation workflow utilizes a classical recommendation process to achieve better results while using minimal resources. It encompasses essential processes like recall, pre-rank, and rank. The workflow also leverages embedding results from content providers to further conserve computational resources.


**WORKFLOW SPECIFICATIONS**

This recommendation workflow is developed under the Terminus Recommend Protocol, which is illustrated below.
![](https://file.bttcdn.com/appstore/recommendreadme/recommend_workflow_notitle.png)

The core element of the recommendation engine is a service called the Knowledge Base. It mainly handles the content source required by the algorithm and manages the recommendation results.

Upon installing this recommendation from the Terminus Market, all processes run completely offline on your local Terminus Edge. The Knowledge Base handles all content retrieval, periodically syncing with the content provider to fetch data packages. As the data first syncs in an unfiltered package, then gets filtered and sorted on your local edge, the content provider remains unaware of your interests.

This recommendation algorithm comprises 2 types of workflows, each with a few steps:
- Recommendation Workflows: 
    - This workflow is executed every 10 minutes to provide the most recent news.
    - The workflow includes recall, pre-rank, and rank programs. The recall program eliminates irrelevant content, leaving approximately 10,000 articles for further sorting. The pre-rank program sorts the recalled content and fetches the full text of top articles. The rank program then fine-tunes the order based on the full-text content, suggesting content that aligns best with your current interests.
    - The contents that recommended is securely stored within knowledge base, and can be accessed via Wise or other compatible reading apps.

- Training Workflow: 
    - This daily workflow modifies the sorting model used by the Recommendation workflow.
    - It uses behavioral data and global news trends stored in the knowledge base to train the recommendation algorithm and update your user embedding.
    - The training results are also stored in the knowledge base.
