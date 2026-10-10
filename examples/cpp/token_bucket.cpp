// C++17 teaching example. Compile: g++ -std=c++17 -O2 -Wall -Wextra -Werror -pthread token_bucket.cpp -o token_bucket
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cmath>
#include <functional>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

class TokenBucket {
public:
    using Clock = std::chrono::steady_clock;
    using Now = std::function<Clock::time_point()>;

    TokenBucket(double capacity, double refill_per_second,
                Now now = [] { return Clock::now(); })
        : capacity_(capacity),
          rate_(refill_per_second),
          now_(std::move(now)),
          last_(now_()),
          tokens_(capacity) {
        if (!std::isfinite(capacity_) || !std::isfinite(rate_) ||
            capacity_ <= 0 || rate_ <= 0)
            throw std::invalid_argument("positive finite limits required");
    }

    bool allow(double cost = 1.0) {
        if (!std::isfinite(cost) || cost <= 0)
            throw std::invalid_argument("positive finite cost required");
        std::lock_guard<std::mutex> guard(mu_);
        const auto next = now_();
        const double seconds =
            std::chrono::duration<double>(next - last_).count();
        if (seconds < 0)
            throw std::logic_error("nonmonotonic injected clock");
        tokens_ = std::min(capacity_, tokens_ + seconds * rate_);
        last_ = next;
        if (tokens_ < cost) return false;
        tokens_ -= cost;
        return true;
    }

private:
    const double capacity_;
    const double rate_;
    Now now_;
    Clock::time_point last_;
    double tokens_;
    std::mutex mu_; // Protects last_ and tokens_ together.
};

int main() {
    using Clock = TokenBucket::Clock;
    auto current = Clock::time_point{};
    TokenBucket limiter(2.0, 1.0, [&] { return current; });
    assert(limiter.allow());
    assert(limiter.allow());
    assert(!limiter.allow());
    current += std::chrono::milliseconds(500);
    assert(!limiter.allow());
    current += std::chrono::milliseconds(500);
    assert(limiter.allow());
    assert(!limiter.allow());
    current += std::chrono::hours(24);
    assert(limiter.allow(2.0));
    assert(!limiter.allow());

    bool rejected = false;
    try { (void)limiter.allow(0); }
    catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    TokenBucket shared(3.0, 1.0 / 1000000.0);
    std::atomic<int> admitted{0};
    std::vector<std::thread> workers;
    for (int i = 0; i < 12; ++i)
        workers.emplace_back([&] { if (shared.allow()) ++admitted; });
    for (auto &worker : workers) worker.join();
    assert(admitted == 3);
}
