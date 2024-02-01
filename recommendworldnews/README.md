**KEY FEATURES**
- **Security and Privacy First**: All recommendation process run on your local Terminus Node, no data send out to any third-party servers.  All your personal behavioral data is encrypted and stored locally.

- **Personalized Content Curation**: The algorithm learns from your interactions, including reads, likes, bookmarks, to build a dynamic user profile.

- **Adaptive Learning**: Automatically adjusts recommendations based on changes in user behavior and global news trends. 

- ** Lightweight Design**: Optimized workflow to ensure minimal resource usage. This recommendation workflow leverages the embedding result from the index providers to conserve compute resources.

- **Zero Maintenance**: This recommendation has a built-in upgrade workflows. It can update the algorithm, data source and workflows by itself.

- **Easy Monitoring**: Captures detailed logs for monitoring the status of the workflow and locating problems.

**WORKFLOW SPECIFICATIONS**
This recommendation is developed under the Terminus Recommend Protocol, which is illustrated below. This recommendation workflow does not require an internet connection except for installation and upgrades. All recommendation process are running offline on your local Terminus Node. Therefore, you don’t have to worry about personal data leaking to third parties. It also doesn't store any of your content or behavioral data, all data sync and management works are done by Terminus OS. 
![](https://www.cflowapps.com/wp-content/uploads/2023/04/Lucidchart.png)

The recommendation algorithm has 2 workflows, each containing a few steps. 
1. Recommendation Workflow. This workflow has 3 steps and runs every 10 mins to ensure you get the latest news.
2. Training Workflow. This workflow runs every day to adjust the content ranking algorithm based on changes in your behavior and global news trends.