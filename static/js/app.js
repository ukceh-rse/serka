document.addEventListener("alpine:init", () => {
    Alpine.data("app", () => ({
        query: '',
        selected_collection: '',
        collections: [],
        results: [],
        answer: '',
        thinking: true,
        splash: true,
        modal: {
            show: false,
            item: '',
            type: '',
            text: '',
        },
        toast: {
            show: false,
            title: 'Toast Title',
            msg: 'Toast Message',
        },
        async search() {
            this.splash = false;
            this.thinking = true;
            this.answer = '';
            this.ragSearch(this);
            try {
                const response = await fetch(`/query/semantic?q=${this.query}&collection=${this.selected_collection}`);
                this.results = await response.json();
            } catch (e) {
                console.error(e);
            } finally {
                this.thinking = false;
            }
        },
        async ragSearch() {
            try {
                const response = await fetch(`/query/rag?q=${this.query}&collection=${this.selected_collection}`);
                answer = await response.json();
                if (answer["result"]["success"]) {
                    this.answer = marked.parse(answer.answer);
                } else {
                    this.answer = answer["result"]["msg"];
                }
            } catch (e) {
                console.error(e);
            }
        },
        async get_collections() {
            try {
                const response = await fetch(`/collections/list`);
                const result = await response.json();
                this.collections = result;
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
        async submit_feedback_modal(item, itemType, query, feedback, type) {
            if (feedback.length < 10) {
                this.showToast('Feedback Error', 'Feedback must be at least 10 characters long');
                return;
            }
            this.give_feedback(item, itemType, query, feedback, type);
            this.modal.text = '';
            this.closeModal();
        },
        async give_feedback(item, itemType, query, feedback, feedbackType) {
            const feedback_obj = { "query": query, "item": item, "itemType": itemType, "feedback": feedback, "type": feedbackType };
            console.log(feedback_obj);
            const response = await fetch(`/feedback/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(feedback_obj),
            });
            const result = await response.json();
            this.showToast('Feedback Submitted', feedbackType + ':"' + feedback + '" for: ' + JSON.stringify(item));
        },
        showToast(title, msg) {
            this.toast.show = true;
            this.toast.title = title;
            this.toast.msg = msg;
            setTimeout(() => {
                this.toast.show = false;
            }, 4000);
        },
        openModal(item, type) {
            this.modal.item = item;
            this.modal.type = type;
            this.modal.show = true;
        },
        closeModal() {
            this.modal.show = false;
        },
    }))
})
