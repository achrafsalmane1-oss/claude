use anchor_lang::prelude::*;

declare_id!("44pCUeEtEaKTLFHtrvvEu78N9Xv9A54yb3TTbTdoqif9");

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────
const STATE_SEED: &[u8] = b"haven_state";
const USER_BALANCE_SEED: &[u8] = b"user_balance";
const VALIDATOR_LIST_SEED: &[u8] = b"validator_list";
const WITHDRAWAL_QUEUE_SEED: &[u8] = b"withdrawal_queue";
const MAX_VALIDATORS: usize = 20;
const MAX_PENDING_WITHDRAWALS: usize = 500;
const MIN_DEPOSIT_LAMPORTS: u64 = 1_000_000; // 0.001 SOL

#[program]
pub mod haven {
    use super::*;

    // ─────────────────────────────────────────
    // initialize — called once by operator at deploy
    // ─────────────────────────────────────────
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let state = &mut ctx.accounts.program_state;
        state.operator = ctx.accounts.operator.key();
        state.total_staked_lamports = 0;
        state.total_users = 0;
        state.is_paused = false;
        state.bump = ctx.bumps.program_state;

        let validator_list = &mut ctx.accounts.validator_list;
        validator_list.validators = Vec::new();
        validator_list.bump = ctx.bumps.validator_list;

        let withdrawal_queue = &mut ctx.accounts.withdrawal_queue;
        withdrawal_queue.requests = Vec::new();
        withdrawal_queue.next_id = 0;
        withdrawal_queue.bump = ctx.bumps.withdrawal_queue;

        emit!(ProgramInitialized {
            operator: state.operator,
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // deposit — pools user SOL into program_state PDA
    // ─────────────────────────────────────────
    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        require!(!ctx.accounts.program_state.is_paused, HavenError::ProgramPaused);
        require!(amount >= MIN_DEPOSIT_LAMPORTS, HavenError::DepositTooSmall);

        // Transfer SOL from payer → program_state PDA (acts as vault)
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.payer.key(),
            &ctx.accounts.program_state.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(
            &ix,
            &[
                ctx.accounts.payer.to_account_info(),
                ctx.accounts.program_state.to_account_info(),
            ],
        )?;

        let is_new_user = ctx.accounts.user_balance.balance_lamports == 0
            && ctx.accounts.user_balance.pending_withdrawal_lamports == 0;

        let user_balance = &mut ctx.accounts.user_balance;
        user_balance.user = ctx.accounts.user_authority.key();
        user_balance.balance_lamports = user_balance
            .balance_lamports
            .checked_add(amount)
            .ok_or(HavenError::Overflow)?;
        user_balance.bump = ctx.bumps.user_balance;

        let state = &mut ctx.accounts.program_state;
        state.total_staked_lamports = state
            .total_staked_lamports
            .checked_add(amount)
            .ok_or(HavenError::Overflow)?;
        if is_new_user {
            state.total_users = state
                .total_users
                .checked_add(1)
                .ok_or(HavenError::Overflow)?;
        }

        emit!(DepositEvent {
            user: ctx.accounts.user_authority.key(),
            amount_lamports: amount,
            new_balance: user_balance.balance_lamports,
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // add_validator — OPERATOR ONLY
    // ─────────────────────────────────────────
    pub fn add_validator(
        ctx: Context<ValidatorOp>,
        validator_vote_pubkey: Pubkey,
    ) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        let vl = &mut ctx.accounts.validator_list;
        require!(vl.validators.len() < MAX_VALIDATORS, HavenError::ValidatorListFull);
        require!(!vl.validators.contains(&validator_vote_pubkey), HavenError::ValidatorAlreadyAdded);
        vl.validators.push(validator_vote_pubkey);
        emit!(ValidatorAdded {
            validator: validator_vote_pubkey,
            operator: ctx.accounts.operator.key(),
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // remove_validator — OPERATOR ONLY
    // ─────────────────────────────────────────
    pub fn remove_validator(
        ctx: Context<ValidatorOp>,
        validator_vote_pubkey: Pubkey,
    ) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        ctx.accounts.validator_list.validators.retain(|v| v != &validator_vote_pubkey);
        emit!(ValidatorRemoved {
            validator: validator_vote_pubkey,
            operator: ctx.accounts.operator.key(),
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // credit_user_reward — OPERATOR ONLY, called per-user during daily distribution
    // ─────────────────────────────────────────
    pub fn credit_user_reward(
        ctx: Context<CreditUserReward>,
        amount_lamports: u64,
    ) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        let ub = &mut ctx.accounts.user_balance;
        ub.balance_lamports = ub
            .balance_lamports
            .checked_add(amount_lamports)
            .ok_or(HavenError::Overflow)?;

        ctx.accounts.program_state.total_staked_lamports = ctx
            .accounts
            .program_state
            .total_staked_lamports
            .checked_add(amount_lamports)
            .ok_or(HavenError::Overflow)?;

        emit!(UserRewarded {
            user: ub.user,
            amount_lamports,
            new_balance: ub.balance_lamports,
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // request_withdrawal — user queues a withdrawal
    // ─────────────────────────────────────────
    pub fn request_withdrawal(ctx: Context<RequestWithdrawal>, amount: u64) -> Result<()> {
        require!(!ctx.accounts.program_state.is_paused, HavenError::ProgramPaused);
        require!(amount > 0, HavenError::ZeroAmount);
        require!(
            ctx.accounts.user_balance.user == ctx.accounts.user.key(),
            HavenError::Unauthorized
        );
        require!(
            amount <= ctx.accounts.user_balance.balance_lamports,
            HavenError::InsufficientBalance
        );

        // Lock the amount
        let ub = &mut ctx.accounts.user_balance;
        ub.balance_lamports = ub.balance_lamports.checked_sub(amount).ok_or(HavenError::Overflow)?;
        ub.pending_withdrawal_lamports = ub
            .pending_withdrawal_lamports
            .checked_add(amount)
            .ok_or(HavenError::Overflow)?;

        // Enqueue
        let queue = &mut ctx.accounts.withdrawal_queue;
        require!(queue.requests.len() < MAX_PENDING_WITHDRAWALS, HavenError::WithdrawalQueueFull);

        let request_id = queue.next_id;
        queue.next_id = queue.next_id.checked_add(1).ok_or(HavenError::Overflow)?;
        queue.requests.push(WithdrawalRequest {
            user: ctx.accounts.user.key(),
            amount_lamports: amount,
            requested_at: Clock::get()?.unix_timestamp,
            id: request_id,
        });

        emit!(WithdrawalRequested {
            user: ctx.accounts.user.key(),
            amount_lamports: amount,
            request_id,
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // operator_withdraw_for_user — OPERATOR ONLY, executes queued withdrawal
    // ─────────────────────────────────────────
    pub fn operator_withdraw_for_user(
        ctx: Context<OperatorWithdraw>,
        amount: u64,
        request_id: u64,
    ) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        require!(!ctx.accounts.program_state.is_paused, HavenError::ProgramPaused);
        require!(amount > 0, HavenError::ZeroAmount);

        let ub = &mut ctx.accounts.user_balance;
        require!(ub.pending_withdrawal_lamports >= amount, HavenError::InsufficientBalance);
        ub.pending_withdrawal_lamports = ub
            .pending_withdrawal_lamports
            .checked_sub(amount)
            .ok_or(HavenError::Overflow)?;

        ctx.accounts.program_state.total_staked_lamports = ctx
            .accounts
            .program_state
            .total_staked_lamports
            .checked_sub(amount)
            .ok_or(HavenError::Overflow)?;

        ctx.accounts.withdrawal_queue.requests.retain(|r| r.id != request_id);

        // Transfer SOL from program_state PDA → user via PDA signer
        let bump = ctx.accounts.program_state.bump;
        let seeds: &[&[u8]] = &[STATE_SEED, &[bump]];
        let signer_seeds = &[seeds];

        let transfer_ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.program_state.key(),
            &ctx.accounts.user.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke_signed(
            &transfer_ix,
            &[
                ctx.accounts.program_state.to_account_info(),
                ctx.accounts.user.to_account_info(),
            ],
            signer_seeds,
        )?;

        emit!(WithdrawalProcessed {
            user: ctx.accounts.user.key(),
            amount_lamports: amount,
            request_id,
            operator: ctx.accounts.operator.key(),
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // pause / unpause — OPERATOR ONLY
    // ─────────────────────────────────────────
    pub fn pause(ctx: Context<OperatorOnly>) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        ctx.accounts.program_state.is_paused = true;
        emit!(ProgramPausedEvent {
            operator: ctx.accounts.operator.key(),
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    pub fn unpause(ctx: Context<OperatorOnly>) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        ctx.accounts.program_state.is_paused = false;
        emit!(ProgramUnpausedEvent {
            operator: ctx.accounts.operator.key(),
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    // ─────────────────────────────────────────
    // transfer_operator — OPERATOR ONLY
    // ─────────────────────────────────────────
    pub fn transfer_operator(ctx: Context<OperatorOnly>, new_operator: Pubkey) -> Result<()> {
        require!(
            ctx.accounts.operator.key() == ctx.accounts.program_state.operator,
            HavenError::Unauthorized
        );
        let old = ctx.accounts.program_state.operator;
        ctx.accounts.program_state.operator = new_operator;
        emit!(OperatorTransferred {
            old_operator: old,
            new_operator,
            timestamp: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }
}

// ─────────────────────────────────────────────
// Account contexts
// ─────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = operator,
        space = ProgramState::SIZE,
        seeds = [STATE_SEED],
        bump
    )]
    pub program_state: Account<'info, ProgramState>,

    #[account(
        init,
        payer = operator,
        space = ValidatorList::SIZE,
        seeds = [VALIDATOR_LIST_SEED],
        bump
    )]
    pub validator_list: Account<'info, ValidatorList>,

    #[account(
        init,
        payer = operator,
        space = WithdrawalQueue::SIZE,
        seeds = [WITHDRAWAL_QUEUE_SEED],
        bump
    )]
    pub withdrawal_queue: Account<'info, WithdrawalQueue>,

    #[account(mut)]
    pub operator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(amount: u64)]
pub struct Deposit<'info> {
    #[account(mut, seeds = [STATE_SEED], bump = program_state.bump)]
    pub program_state: Account<'info, ProgramState>,

    #[account(
        init_if_needed,
        payer = payer,
        space = UserBalance::SIZE,
        seeds = [USER_BALANCE_SEED, user_authority.key().as_ref()],
        bump
    )]
    pub user_balance: Account<'info, UserBalance>,

    /// The logical user this deposit is attributed to (may differ from payer —
    /// the operator can deposit on a user's behalf).
    /// CHECK: We only use this as a seed for user_balance and event emission.
    pub user_authority: UncheckedAccount<'info>,

    /// Funds come from this account (operator wallet in production).
    #[account(mut)]
    pub payer: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ValidatorOp<'info> {
    #[account(mut, seeds = [STATE_SEED], bump = program_state.bump)]
    pub program_state: Account<'info, ProgramState>,

    #[account(mut, seeds = [VALIDATOR_LIST_SEED], bump = validator_list.bump)]
    pub validator_list: Account<'info, ValidatorList>,

    #[account(mut)]
    pub operator: Signer<'info>,
}

#[derive(Accounts)]
pub struct CreditUserReward<'info> {
    #[account(mut, seeds = [STATE_SEED], bump = program_state.bump)]
    pub program_state: Account<'info, ProgramState>,

    #[account(
        mut,
        seeds = [USER_BALANCE_SEED, user_balance.user.as_ref()],
        bump = user_balance.bump
    )]
    pub user_balance: Account<'info, UserBalance>,

    #[account(mut)]
    pub operator: Signer<'info>,
}

#[derive(Accounts)]
pub struct RequestWithdrawal<'info> {
    #[account(seeds = [STATE_SEED], bump = program_state.bump)]
    pub program_state: Account<'info, ProgramState>,

    #[account(
        mut,
        seeds = [USER_BALANCE_SEED, user.key().as_ref()],
        bump = user_balance.bump
    )]
    pub user_balance: Account<'info, UserBalance>,

    #[account(mut, seeds = [WITHDRAWAL_QUEUE_SEED], bump = withdrawal_queue.bump)]
    pub withdrawal_queue: Account<'info, WithdrawalQueue>,

    #[account(mut)]
    pub user: Signer<'info>,
}

#[derive(Accounts)]
pub struct OperatorWithdraw<'info> {
    #[account(mut, seeds = [STATE_SEED], bump = program_state.bump)]
    pub program_state: Account<'info, ProgramState>,

    #[account(
        mut,
        seeds = [USER_BALANCE_SEED, user.key().as_ref()],
        bump = user_balance.bump
    )]
    pub user_balance: Account<'info, UserBalance>,

    #[account(mut, seeds = [WITHDRAWAL_QUEUE_SEED], bump = withdrawal_queue.bump)]
    pub withdrawal_queue: Account<'info, WithdrawalQueue>,

    /// CHECK: Recipient of withdrawn SOL — validated via user_balance.user in the instruction.
    #[account(mut)]
    pub user: UncheckedAccount<'info>,

    #[account(mut)]
    pub operator: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct OperatorOnly<'info> {
    #[account(mut, seeds = [STATE_SEED], bump = program_state.bump)]
    pub program_state: Account<'info, ProgramState>,

    #[account(mut)]
    pub operator: Signer<'info>,
}

// ─────────────────────────────────────────────
// State account definitions
// ─────────────────────────────────────────────

#[account]
pub struct ProgramState {
    pub operator: Pubkey,           // 32
    pub total_staked_lamports: u64, // 8
    pub total_users: u64,           // 8
    pub is_paused: bool,            // 1
    pub bump: u8,                   // 1
}

impl ProgramState {
    pub const SIZE: usize = 8 + 32 + 8 + 8 + 1 + 1 + 64;
}

#[account]
pub struct UserBalance {
    pub user: Pubkey,                       // 32
    pub balance_lamports: u64,              // 8
    pub pending_withdrawal_lamports: u64,   // 8
    pub bump: u8,                           // 1
}

impl UserBalance {
    pub const SIZE: usize = 8 + 32 + 8 + 8 + 1 + 32;
}

#[account]
pub struct ValidatorList {
    pub validators: Vec<Pubkey>, // 4 + 32 * MAX_VALIDATORS
    pub bump: u8,
}

impl ValidatorList {
    pub const SIZE: usize = 8 + 4 + (32 * MAX_VALIDATORS) + 1 + 32;
}

#[account]
pub struct WithdrawalQueue {
    pub requests: Vec<WithdrawalRequest>,
    pub next_id: u64,
    pub bump: u8,
}

impl WithdrawalQueue {
    // Each WithdrawalRequest: 32 + 8 + 8 + 8 = 56 bytes
    pub const SIZE: usize = 8 + 4 + (56 * MAX_PENDING_WITHDRAWALS) + 8 + 1 + 64;
}

// ─────────────────────────────────────────────
// Data types
// ─────────────────────────────────────────────

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct WithdrawalRequest {
    pub user: Pubkey,
    pub amount_lamports: u64,
    pub requested_at: i64,
    pub id: u64,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct RewardEntry {
    pub user: Pubkey,
    pub amount_lamports: u64,
}

// ─────────────────────────────────────────────
// Events
// ─────────────────────────────────────────────

#[event]
pub struct ProgramInitialized {
    pub operator: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct DepositEvent {
    pub user: Pubkey,
    pub amount_lamports: u64,
    pub new_balance: u64,
    pub timestamp: i64,
}

#[event]
pub struct ValidatorAdded {
    pub validator: Pubkey,
    pub operator: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct ValidatorRemoved {
    pub validator: Pubkey,
    pub operator: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct UserRewarded {
    pub user: Pubkey,
    pub amount_lamports: u64,
    pub new_balance: u64,
    pub timestamp: i64,
}

#[event]
pub struct WithdrawalRequested {
    pub user: Pubkey,
    pub amount_lamports: u64,
    pub request_id: u64,
    pub timestamp: i64,
}

#[event]
pub struct WithdrawalProcessed {
    pub user: Pubkey,
    pub amount_lamports: u64,
    pub request_id: u64,
    pub operator: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct ProgramPausedEvent {
    pub operator: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct ProgramUnpausedEvent {
    pub operator: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct OperatorTransferred {
    pub old_operator: Pubkey,
    pub new_operator: Pubkey,
    pub timestamp: i64,
}

// ─────────────────────────────────────────────
// Errors
// ─────────────────────────────────────────────

#[error_code]
pub enum HavenError {
    #[msg("Caller is not the operator")]
    Unauthorized,
    #[msg("Program is paused")]
    ProgramPaused,
    #[msg("Deposit amount too small (min 0.001 SOL)")]
    DepositTooSmall,
    #[msg("Insufficient balance for this operation")]
    InsufficientBalance,
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Arithmetic overflow")]
    Overflow,
    #[msg("Validator list is full (max 20)")]
    ValidatorListFull,
    #[msg("Validator already in approved list")]
    ValidatorAlreadyAdded,
    #[msg("Withdrawal queue is full (max 500)")]
    WithdrawalQueueFull,
}
