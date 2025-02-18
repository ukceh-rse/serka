document.addEventListener("alpine:init", () => {
    Alpine.data("app", () => ({
        query: '',
        selected_collection: '',
        collections: [],
        results: [],
        answer: '',
        thinking: true,
        splash: true,
        feedbackItem: '',
        feedbackText: '',
        showModal: false,
        async search() {
            this.splash = false;
            this.thinking = true;
            this.answer = '';
            this.ragSearch(this);
            try {
                const response = await fetch(`/search?q=${this.query}&collection=${this.selected_collection}`);
                this.results = await response.json();
            } catch (e) {
                console.error(e);
            } finally {
                this.thinking = false;
            }
        },
        async ragSearch() {
            try {
                const response = await fetch(`/rag?q=${this.query}&collection=${this.selected_collection}`);
                answer = await response.json();
                this.answer = marked.parse(answer.answer);
            } catch (e) {
                console.error(e);
            }
        },
        async get_collections() {
            try {
                const response = await fetch(`/list`);
                const result = await response.json();
                this.collections = result.collections;
                if (this.collections.length > 0)
                    this.selected_collection = this.collections[0];
                this.thinking = false;
            } catch (e) {
                console.error(e);
            }
        },
        async feedback(event) {
            console.log('Giving feedback...');
            console.log(event.target);
        },
        openModal(feedbackItem) {
            this.feedbackItem = feedbackItem;
            this.showModal = true;
        },
        closeModal() {
            this.showModal = false;
        },
    }))
})
